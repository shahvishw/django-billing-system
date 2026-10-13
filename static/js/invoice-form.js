/* static/js/invoice-form.js  (NEW FILE)
   Everything the "New invoice" screen does in the browser.
   Talks to the same two endpoints as before:
     - check_customer  (GET ?phone=...)
     - search_products (GET ?q=...)
   and submits the same fields: customer_id, catalog_items[],
   quantities[], discounts[].
*/

(function () {
    'use strict';

    var form = document.getElementById('invoiceForm');
    if (!form) return;

    var CHECK_URL = form.dataset.checkUrl;
    var SEARCH_URL = form.dataset.searchUrl;
    var ADD_CUSTOMER_URL = form.dataset.addCustomerUrl;
    var TAX_RATE = parseFloat(form.dataset.taxRate);
    if (isNaN(TAX_RATE)) TAX_RATE = 0;
    var DISCOUNT_MODE = form.dataset.discountMode || 'per_item';

    function $(id) { return document.getElementById(id); }

    var phoneInput = $('custPhone');
    var checkBtn = $('checkBtn');
    var statusBox = $('customerStatus');
    var customerIdInput = $('customerId');

    var searchInput = $('productSearch');
    var results = $('productResults');

    var itemsBody = $('invoiceItems');
    var tableWrap = $('itemsTableWrap');
    var itemsEmpty = $('itemsEmpty');
    var hiddenFields = $('hiddenFields');
    var flashBox = $('invoiceFlash');

    var subtotalEl = $('subtotal');
    var taxEl = $('tax');
    var totalEl = $('total');
    var subtotalDiscountWrap = form.querySelector('.js-subtotal-discount');
    var subtotalDiscountInput = $('subtotalDiscount');
    var subtotalDiscountNote = $('subtotalDiscountNote');
    var countEl = $('itemCount');
    var submitBtn = $('submitBtn');
    var chkCustomer = $('chkCustomer');
    var chkItems = $('chkItems');

    var customerId = '';
    var customerCheckSequence = 0;
    var items = [];          // the invoice lines
    var lastResults = {};    // product search results, keyed by id
    var submitting = false;


    /* =====================================================
       SMALL HELPERS
    ===================================================== */

    // Makes any text safe to put inside HTML (stops product names breaking the page)
    function esc(value) {
        return String(value === null || value === undefined ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function round2(n) {
        return Math.round((n + Number.EPSILON) * 100) / 100;
    }

    function fmt(n) {
        return '\u20B9' + n.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    var NOTICE_ICONS = {
        success: 'bi-check-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        danger: 'bi-x-circle-fill'
    };

    function noticeHtml(type, inner) {
        return '<div class="ip-notice ip-notice-' + type + '">' +
            '<i class="bi ' + NOTICE_ICONS[type] + '"></i>' +
            '<div class="flex-grow-1">' + inner + '</div></div>';
    }

    var flashTimer;
    function flash(type, message) {
        clearTimeout(flashTimer);
        flashBox.innerHTML = noticeHtml(type, esc(message));
        flashTimer = setTimeout(function () { flashBox.innerHTML = ''; }, 4500);
    }

    function unitPrice(item) {
        if (item.mrp === null) return 0;
        return round2(item.mrp * (1 - item.discount / 100));
    }


    /* =====================================================
       CUSTOMER
    ===================================================== */

    function showStatus(type, inner) {
        statusBox.innerHTML = noticeHtml(type, inner);
    }

    function resetCustomer() {
        customerCheckSequence++;
        checkBtn.disabled = false;
        customerId = '';
        customerIdInput.value = '';
        statusBox.innerHTML = '';
        refresh();
    }

    function checkCustomer() {
        var phone = phoneInput.value.trim();

        if (!phone) {
            showStatus('warning', 'Enter the customer\u2019s phone number first.');
            return;
        }

        var requestSequence = ++customerCheckSequence;
        checkBtn.disabled = true;

        fetch(CHECK_URL + '?phone=' + encodeURIComponent(phone), {
            headers: { 'Accept': 'application/json' }
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (requestSequence !== customerCheckSequence) return;

                if (data.error) {
                    resetCustomer();
                    showStatus('danger', esc(data.error));
                } else if (data.exists) {
                    customerId = String(data.customer_id);
                    customerIdInput.value = customerId;
                    showStatus(
                        'success',
                        '<strong>' + esc(data.name) + '</strong> ' +
                        '<span class="ip-muted">\u00B7 customer found</span>' +
                        '<button type="button" class="ip-link-btn" data-action="change-customer">Change</button>'
                    );
                } else {
                    resetCustomer();
                    showStatus(
                        'warning',
                        'No customer with this number yet. ' +
                        '<a href="' + esc(ADD_CUSTOMER_URL) + '" class="ip-link">Add new customer</a>'
                    );
                }
            })
            .catch(function () {
                if (requestSequence !== customerCheckSequence) return;

                resetCustomer();
                showStatus('danger', 'Could not check the customer. Please try again.');
            })
            .then(function () {
                if (requestSequence !== customerCheckSequence) return;

                checkBtn.disabled = false;
                refresh();
            });
    }

    checkBtn.addEventListener('click', checkCustomer);

    // Changing the phone number after a customer was found clears that customer
    phoneInput.addEventListener('input', resetCustomer);

    statusBox.addEventListener('click', function (e) {
        if (e.target.closest('[data-action="change-customer"]')) {
            resetCustomer();
            phoneInput.focus();
            phoneInput.select();
        }
    });


    /* =====================================================
       PRODUCT SEARCH
    ===================================================== */

    var searchTimer;
    var searchSeq = 0;

    searchInput.addEventListener('input', function () {
        clearTimeout(searchTimer);
        var q = this.value.trim();
        var requestSequence = ++searchSeq;

        if (q.length < 2) {
            results.innerHTML = '';
            lastResults = {};
            return;
        }

        results.innerHTML = '<li class="ip-result-note">Searching... </li>';
        lastResults = {};
        searchTimer = setTimeout(function () {
            runSearch(q, requestSequence);
        }, 250);
    });

    function runSearch(q, requestSequence) {
        results.innerHTML = '<li class="ip-result-note">Searching\u2026</li>';

        fetch(SEARCH_URL + '?q=' + encodeURIComponent(q), {
            headers: { 'Accept': 'application/json' }
        })
            .then(function (res) { return res.json(); })
            .then(function (products) {
                if (requestSequence !== searchSeq) return;
                renderResults(products);
            })
            .catch(function () {
                if (requestSequence !== searchSeq) return;
                results.innerHTML = '<li class="ip-result-note">Could not load products. Please try again.</li>';
            });
    }

    function renderResults(products) {
        lastResults = {};

        if (!products.length) {
            results.innerHTML = '<li class="ip-result-note">No products found.</li>';
            return;
        }

        results.innerHTML = products.map(function (p) {
            lastResults[p.catalog_item_id] = p;

            var isProduct = p.item_type === 'product';
            var outOfStock = isProduct && p.stock <= 0;
            var missingMrp = p.mrp === null;
            var disabled = (outOfStock || missingMrp) ? ' disabled' : '';

            var stockText = missingMrp
                ? 'MRP missing'
                : (isProduct
                    ? (outOfStock ? 'Out of stock' : 'Stock ' + p.stock)
                    : 'Service');

            return '<li class="ip-result" data-id="' + esc(p.catalog_item_id) + '">' +
                '<div class="ip-result-info">' +
                    '<strong>' + esc(p.name) + '</strong>' +
                    (p.brand ? '<small>' + esc(p.brand) + '</small>' : '') +
                '</div>' +
                '<div class="ip-result-meta">' +
                    (p.mrp !== null ? '<span class="ip-chip ip-chip-price">MRP ' + fmt(p.mrp) + '</span>' : '') +
                    (DISCOUNT_MODE === 'per_item' ? '<span class="ip-chip">Default discount ' + p.default_discount_percent + '%</span>' : '') +
                    '<span class="ip-chip' + (outOfStock ? ' ip-chip-danger' : '') + '">' + stockText + '</span>' +
                '</div>' +
                '<div class="ip-result-add">' +
                    '<input type="number" class="ip-qty" min="1" value="1" aria-label="Quantity"' + disabled + '>' +
                    '<button type="button" class="ip-btn ip-btn-primary ip-btn-sm" data-action="add"' + disabled + '>Add</button>' +
                '</div>' +
            '</li>';
        }).join('');
    }

    function addFromResult(li) {
        var product = lastResults[li.dataset.id];
        if (!product) return;

        var qty = parseInt(li.querySelector('.ip-qty').value, 10);
        if (!qty || qty < 1) qty = 1;

        if (addItem(product, qty)) {
            results.innerHTML = '';
            searchInput.value = '';
            searchInput.focus();
        }
    }

    results.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-action="add"]');
        if (btn) addFromResult(btn.closest('.ip-result'));
    });


    /* =====================================================
       INVOICE ITEMS
    ===================================================== */

    function findItem(id) {
        for (var i = 0; i < items.length; i++) {
            if (items[i].id === id) return items[i];
        }
        return null;
    }

    function addItem(p, qty) {
        var isProduct = p.item_type === 'product';
        var existing = findItem(String(p.catalog_item_id));
        var newQty = (existing ? existing.qty : 0) + qty;

        if (isProduct && newQty > p.stock) {
            flash('danger', 'Only ' + p.stock + ' of \u201C' + p.name + '\u201D in stock.');
            return false;
        }

        if (existing) {
            existing.qty = newQty;      // same product again: just increase quantity
        } else {
            items.push({
                id: String(p.catalog_item_id),
                name: p.name,
                brand: p.brand || '',
                type: p.item_type,
                mrp: p.mrp,
                maxDiscount: p.max_discount_percent,
                defaultDiscount: p.default_discount_percent,
                stock: p.stock,
                qty: qty,
                discount: DISCOUNT_MODE === 'per_item' ? Math.min(p.default_discount_percent, p.max_discount_percent) : 0
            });
        }

        renderItems();
        return true;
    }

    function rowHtml(item) {
        var isProduct = item.type === 'product';

        return '<tr data-id="' + esc(item.id) + '">' +
            '<td><strong>' + esc(item.name) + '</strong>' +
                (item.brand ? '<div class="ip-muted small">' + esc(item.brand) + '</div>' : '') +
            '</td>' +
            '<td class="ip-num">' + (item.mrp === null ? '\u2014' : fmt(item.mrp)) + '</td>' +
            '<td class="js-per-item-discount"' + (DISCOUNT_MODE === 'per_item' ? '' : ' style="display:none;"') + '>' +
                '<input type="number" class="ip-qty js-discount" min="0" max="' + item.maxDiscount + '" step="0.01" value="' + item.discount + '">' +
                '<div class="ip-row-note js-discount-note">Max ' + item.maxDiscount + '%</div>' +
            '</td>' +
            '<td class="ip-num js-unit-price">' + (item.mrp === null ? '\u2014' : fmt(unitPrice(item))) + '</td>' +
            '<td>' +
                '<input type="number" class="ip-qty js-qty" min="1"' + (isProduct ? ' max="' + item.stock + '"' : '') + ' value="' + item.qty + '">' +
                '<div class="ip-row-note js-qty-note">' + (isProduct ? 'In stock: ' + item.stock : 'Service') + '</div>' +
            '</td>' +
            '<td class="ip-num js-line-total"><strong>' + fmt(unitPrice(item) * item.qty) + '</strong></td>' +
            '<td class="text-end">' +
                '<button type="button" class="ip-icon-btn text-danger" data-action="remove" title="Remove item">' +
                    '<i class="bi bi-x-lg"></i>' +
                '</button>' +
            '</td>' +
        '</tr>';
    }

    function renderItems() {
        itemsBody.innerHTML = items.map(rowHtml).join('');
        tableWrap.style.display = items.length ? '' : 'none';
        itemsEmpty.style.display = items.length ? 'none' : '';
        refresh();
    }

    // Reads one row's inputs, keeps them inside the allowed limits, updates totals
    function syncRow(tr) {
        var item = findItem(tr.dataset.id);
        if (!item) return;

        var qtyInput = tr.querySelector('.js-qty');
        var discInput = tr.querySelector('.js-discount');
        var qtyNote = tr.querySelector('.js-qty-note');
        var discNote = tr.querySelector('.js-discount-note');
        var isProduct = item.type === 'product';

        var qty = parseInt(qtyInput.value, 10);
        var disc = parseFloat(discInput.value);

        // ---- quantity ----
        qtyNote.classList.remove('is-warning');
        qtyNote.textContent = isProduct ? 'In stock: ' + item.stock : 'Service';

        if (isNaN(qty) || qty < 1) {
            qty = item.qty;                       // typing in progress: keep last good value
        } else if (isProduct && qty > item.stock) {
            qty = item.stock;
            qtyInput.value = qty;
            qtyNote.textContent = 'Only ' + item.stock + ' in stock';
            qtyNote.classList.add('is-warning');
        }

        // ---- discount ----
        discNote.classList.remove('is-warning');
        discNote.textContent = 'Max ' + item.maxDiscount + '%';

        if (isNaN(disc) || disc < 0) {
            disc = isNaN(disc) ? item.discount : 0;
        } else if (disc > item.maxDiscount) {
            disc = item.maxDiscount;
            discInput.value = disc;
            discNote.textContent = 'Max allowed is ' + item.maxDiscount + '%';
            discNote.classList.add('is-warning');
        }

        item.qty = qty;
        item.discount = disc;

        tr.querySelector('.js-unit-price').textContent = fmt(unitPrice(item));
        tr.querySelector('.js-line-total').innerHTML = '<strong>' + fmt(unitPrice(item) * item.qty) + '</strong>';
        refresh();
    }

    itemsBody.addEventListener('input', function (e) {
        var tr = e.target.closest('tr');
        if (tr) syncRow(tr);
    });

    itemsBody.addEventListener('change', function (e) {
        // when the user leaves a field, show the cleaned-up value
        var tr = e.target.closest('tr');
        if (!tr) return;
        var item = findItem(tr.dataset.id);
        if (!item) return;
        tr.querySelector('.js-qty').value = item.qty;
        tr.querySelector('.js-discount').value = item.discount;
    });

    itemsBody.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-action="remove"]');
        if (!btn) return;

        var id = btn.closest('tr').dataset.id;
        items = items.filter(function (item) { return item.id !== id; });
        renderItems();
    });


    /* =====================================================
       TOTALS + READY STATE
    ===================================================== */

    function setCheck(el, done) {
        el.classList.toggle('is-done', done);
        el.querySelector('i').className = done ? 'bi bi-check-circle-fill' : 'bi bi-circle';
    }

    function refresh() {
        var grossSubtotal = 0;
        var fields = '';

        items.forEach(function (item) {
            grossSubtotal += unitPrice(item) * item.qty;

            fields +=
                '<input type="hidden" name="catalog_items[]" value="' + esc(item.id) + '">' +
                '<input type="hidden" name="quantities[]" value="' + item.qty + '">' +
                '<input type="hidden" name="discounts[]" value="' + item.discount.toFixed(2) + '">';
        });

        if (DISCOUNT_MODE === 'subtotal') {
            var subtotalDiscount = parseFloat(subtotalDiscountInput.value);
            if (isNaN(subtotalDiscount) || subtotalDiscount < 0) subtotalDiscount = 0;
            if (subtotalDiscount > 100) subtotalDiscount = 100;
            subtotalDiscountInput.value = subtotalDiscount;
            subtotalDiscountNote.textContent = 'Discount ' + subtotalDiscount + '% on subtotal';
            hiddenFields.innerHTML = fields + '<input type="hidden" name="subtotal_discount" value="' + subtotalDiscount.toFixed(2) + '">';
        } else {
            hiddenFields.innerHTML = fields + '<input type="hidden" name="subtotal_discount" value="0.00">';
        }

        grossSubtotal = round2(grossSubtotal);
        var taxableSubtotal = grossSubtotal;
        if (DISCOUNT_MODE === 'subtotal') {
            var appliedSubtotalDiscount = parseFloat(subtotalDiscountInput.value) || 0;
            taxableSubtotal = round2(grossSubtotal * (1 - appliedSubtotalDiscount / 100));
        }
        var tax = round2(taxableSubtotal * TAX_RATE);

        subtotalEl.textContent = fmt(grossSubtotal);
        taxEl.textContent = fmt(tax);
        totalEl.textContent = fmt(round2(taxableSubtotal + tax));
        countEl.textContent = items.length;

        var hasCustomer = !!customerId;
        var hasItems = items.length > 0;

        setCheck(chkCustomer, hasCustomer);
        setCheck(chkItems, hasItems);

        submitBtn.disabled = !(hasCustomer && hasItems) || submitting;
    }


    if (DISCOUNT_MODE === 'subtotal') {
        subtotalDiscountWrap.style.display = '';
        if (subtotalDiscountInput) {
            subtotalDiscountInput.addEventListener('input', refresh);
        }
    }


    /* =====================================================
       KEYBOARD + SUBMIT
    ===================================================== */

    // Enter must never submit the whole invoice by accident
    form.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' || e.target.tagName !== 'INPUT') return;

        e.preventDefault();

        if (e.target === phoneInput) {
            checkCustomer();
        } else if (e.target.closest('.ip-result')) {
            addFromResult(e.target.closest('.ip-result'));
        }
    });

    form.addEventListener('submit', function (e) {
        if (!customerId || !items.length) {
            e.preventDefault();
            flash('warning', 'Select a customer and add at least one item first.');
            return;
        }

        submitting = true;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Creating\u2026';
    });

    // Warn before leaving the page with unsaved items
    window.addEventListener('beforeunload', function (e) {
        if (items.length && !submitting) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    refresh();

})();
