from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import uuid

from django.db import transaction

from audit.models import AuditLog
from audit.services import log_action
from customers.models import Customer
from organizations.models import Organization
from products.models import CatalogItem

from .models import Invoice, InvoiceItem


MONEY_QUANTUM = Decimal('0.01')
MAX_INVOICE_AMOUNT = Decimal('99999999.99')
MAX_ITEM_QUANTITY = 2_147_483_647


class InvoiceCreationError(Exception):
    """A validation error that can be shown safely to the invoice user."""


def _money(value):
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _parse_percent(raw_value, field_name):
    try:
        value = Decimal(raw_value)
    except (InvalidOperation, TypeError, ValueError):
        raise InvoiceCreationError(f'{field_name} must be a valid percentage.')

    if (
        not value.is_finite()
        or value < Decimal('0.00')
        or value > Decimal('100.00')
    ):
        raise InvoiceCreationError(f'{field_name} must be between 0 and 100.')

    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _parse_due_date(raw_value):
    if not raw_value:
        return None

    try:
        return date.fromisoformat(raw_value)
    except (TypeError, ValueError):
        raise InvoiceCreationError('Enter a valid due date.')


def _get_invoice_lines(catalog_item_ids, quantities, discount_percentages, discount_mode):
    if not catalog_item_ids:
        raise InvoiceCreationError('Add at least one product before creating an invoice.')

    if len(catalog_item_ids) != len(quantities):
        raise InvoiceCreationError('Invoice item data is incomplete. Please try again.')

    if discount_mode == Organization.DiscountMode.PER_ITEM:
        if discount_percentages is None:
            discount_percentages = ['0'] * len(catalog_item_ids)
        if len(catalog_item_ids) != len(discount_percentages):
            raise InvoiceCreationError('Invoice discount data is incomplete. Please try again.')
    else:
        discount_percentages = ['0'] * len(catalog_item_ids)

    invoice_lines = {}
    stock_quantities = defaultdict(int)

    for raw_catalog_item_id, raw_quantity, raw_discount in zip(
        catalog_item_ids, quantities, discount_percentages,
    ):
        try:
            catalog_item_id = uuid.UUID(raw_catalog_item_id)
        except (TypeError, ValueError, AttributeError):
            raise InvoiceCreationError('One selected product is invalid.')

        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            raise InvoiceCreationError('Each product quantity must be a whole number.')

        if quantity <= 0:
            raise InvoiceCreationError('Each product quantity must be at least 1.')
        if quantity > MAX_ITEM_QUANTITY:
            raise InvoiceCreationError(
                f'Quantity cannot exceed {MAX_ITEM_QUANTITY:,} per item.'
            )

        discount_percent = _parse_percent(raw_discount, 'Each product discount')
        line_key = (catalog_item_id, discount_percent)
        invoice_lines[line_key] = invoice_lines.get(line_key, 0) + quantity
        stock_quantities[catalog_item_id] += quantity
        if invoice_lines[line_key] > MAX_ITEM_QUANTITY:
            raise InvoiceCreationError(
                f'Combined quantity cannot exceed {MAX_ITEM_QUANTITY:,} per item.'
            )

    return invoice_lines, stock_quantities


def create_invoice(
    *,
    organization,
    customer_id,
    catalog_item_ids,
    quantities,
    discount_percentages=None,
    subtotal_discount_percent='0',
    due_date=None,
    actor=None,
):
    discount_mode = organization.discount_mode
    invoice_lines, stock_quantities = _get_invoice_lines(
        catalog_item_ids,
        quantities,
        discount_percentages,
        discount_mode,
    )

    subtotal_discount_percent = _parse_percent(
        subtotal_discount_percent,
        'Invoice discount',
    )
    due_date = _parse_due_date(due_date)
    if discount_mode == Organization.DiscountMode.PER_ITEM:
        subtotal_discount_percent = Decimal('0.00')

    try:
        customer_uuid = uuid.UUID(customer_id)
    except (TypeError, ValueError, AttributeError):
        raise InvoiceCreationError('Select an existing customer before creating an invoice.')

    with transaction.atomic():
        try:
            customer = Customer.objects.get(
                customer_id=customer_uuid,
                organization=organization,
            )
        except Customer.DoesNotExist:
            raise InvoiceCreationError('The selected customer is unavailable.')

        catalog_items = list(
            CatalogItem.objects.select_for_update().filter(
                organization=organization,
                product_id__in=stock_quantities.keys(),
                is_active=True,
            ).order_by('product_id')
        )
        catalog_items_by_id = {item.product_id: item for item in catalog_items}

        if set(stock_quantities) - set(catalog_items_by_id):
            raise InvoiceCreationError('One or more selected products are inactive or unavailable.')

        for catalog_item_id, requested_quantity in stock_quantities.items():
            catalog_item = catalog_items_by_id[catalog_item_id]
            if (
                catalog_item.item_type == CatalogItem.ItemType.PRODUCT
                and requested_quantity > catalog_item.stock_quantity
            ):
                raise InvoiceCreationError(
                    f'Insufficient stock for "{catalog_item.name}". '
                    f'Available: {catalog_item.stock_quantity}; Requested: {requested_quantity}.'
                )

        invoice = Invoice.objects.create(
            organization=organization,
            customer=customer,
            invoice_number=f'INV-{uuid.uuid4().hex[:16].upper()}',
            due_date=due_date,
            template_key=organization.invoice_template,
            tax_rate_percent=organization.tax_rate_percent,
        )

        gross_subtotal = Decimal('0.00')
        item_discount_amount = Decimal('0.00')

        for (catalog_item_id, discount_percent), requested_quantity in invoice_lines.items():
            catalog_item = catalog_items_by_id[catalog_item_id]

            if discount_mode == Organization.DiscountMode.PER_ITEM:
                if discount_percent > catalog_item.max_discount_percent:
                    raise InvoiceCreationError(
                        f'Discount for "{catalog_item.name}" exceeds the allowed maximum of '
                        f'{catalog_item.max_discount_percent}%.'
                    )
                applied_discount = discount_percent
            else:
                applied_discount = Decimal('0.00')

            if catalog_item.mrp is None:
                raise InvoiceCreationError(
                    f'Add an MRP for "{catalog_item.name}" before creating an invoice.'
                )

            mrp = _money(catalog_item.mrp)
            line_gross = mrp * requested_quantity
            final_unit_price = _money(
                mrp * (Decimal('100.00') - applied_discount) / Decimal('100.00')
            )
            line_total = final_unit_price * requested_quantity
            gross_subtotal += line_gross
            item_discount_amount += line_gross - line_total

            InvoiceItem.objects.create(
                invoice=invoice,
                catalog_item=catalog_item,
                item_name=catalog_item.name,
                quantity=requested_quantity,
                mrp=catalog_item.mrp,
                discount_percent=applied_discount,
                final_unit_price=final_unit_price,
            )

        if discount_mode == Organization.DiscountMode.SUBTOTAL:
            discount_amount = _money(
                gross_subtotal * subtotal_discount_percent / Decimal('100.00')
            )
            taxable_subtotal = _money(gross_subtotal - discount_amount)
            subtotal = _money(gross_subtotal)
        else:
            discount_amount = Decimal('0.00')
            taxable_subtotal = _money(gross_subtotal - item_discount_amount)
            subtotal = taxable_subtotal
            subtotal_discount_percent = Decimal('0.00')

        tax_rate = organization.tax_rate_percent / Decimal('100.00')
        tax = _money(taxable_subtotal * tax_rate)
        total = _money(taxable_subtotal + tax)

        if any(
            amount > MAX_INVOICE_AMOUNT
            for amount in (subtotal, discount_amount, tax, total)
        ):
            raise InvoiceCreationError(
                'This invoice exceeds the maximum supported amount. '
                'Split it into smaller invoices.'
            )

        for catalog_item_id, requested_quantity in stock_quantities.items():
            catalog_item = catalog_items_by_id[catalog_item_id]
            if catalog_item.item_type == CatalogItem.ItemType.PRODUCT:
                catalog_item.stock_quantity -= requested_quantity
                catalog_item.save(update_fields=['stock_quantity'])

        invoice.subtotal = subtotal
        invoice.discount_percent = subtotal_discount_percent
        invoice.discount_amount = discount_amount
        invoice.tax = tax
        invoice.total = total
        invoice.save(update_fields=['subtotal', 'discount_percent', 'discount_amount', 'tax', 'total'])

        if actor is not None:
            log_action(
                organization=organization,
                actor=actor,
                action=AuditLog.Action.INVOICE_CREATED,
                target_type='invoice',
                target_id=invoice.pk,
                description=f'Created invoice {invoice.invoice_number} for {customer.name}.',
            )

    return invoice
