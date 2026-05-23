from django.http import JsonResponse
from .models import Product

def search_products(request):
    query = request.GET.get('q', '')
    products = Product.objects.filter(name__icontains=query)[:10]

    data = [{
        'product_id' : p.product_id,
        'name': p.name,
        'brand' : p.brand,
        'price': float(p.price),
        'stock': p.quantity
    } for p in products]

    return JsonResponse(data, safe=False)
