"""
Integration tests for SerpantSupply REST API.
Run with: python manage.py test tests
"""
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from marketplace.models import Product, Purchase


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_success(self):
        res = self.client.post('/api/auth/register/', json.dumps({
            'username': 'testuser', 'email': 'test@example.com',
            'password': 'SecurePass123', 'password2': 'SecurePass123'
        }), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertEqual(data['user']['username'], 'testuser')

    def test_register_password_mismatch(self):
        res = self.client.post('/api/auth/register/', json.dumps({
            'username': 'u2', 'email': 'u2@example.com',
            'password': 'Pass1234', 'password2': 'WrongPass'
        }), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('password', res.json())

    def test_register_duplicate_email(self):
        User.objects.create_user('existing', 'dup@example.com', 'pass12345')
        res = self.client.post('/api/auth/register/', json.dumps({
            'username': 'newuser', 'email': 'dup@example.com',
            'password': 'Pass1234', 'password2': 'Pass1234'
        }), content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_login_jwt(self):
        User.objects.create_user('jwtuser', 'jwt@example.com', 'JwtPass123')
        res = self.client.post('/api/auth/login/', json.dumps({
            'username': 'jwtuser', 'password': 'JwtPass123'
        }), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.json())

    def test_me_requires_auth(self):
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.status_code, 401)

    def test_me_with_token(self):
        user = User.objects.create_user('meuser', 'me@example.com', 'MePass123')
        login_res = self.client.post('/api/auth/login/', json.dumps({
            'username': 'meuser', 'password': 'MePass123'
        }), content_type='application/json')
        token = login_res.json()['access']
        res = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['username'], 'meuser')


class ProductAPITests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller', 'seller@example.com', 'SellerPass1')
        self.buyer = User.objects.create_user('buyer', 'buyer@example.com', 'BuyerPass1')
        self.product = Product.objects.create(
            seller=self.seller, name='Test Snake', price=49.99,
            description='A test product', condition='New'
        )
        # Get tokens
        res = self.client.post('/api/auth/login/', json.dumps({
            'username': 'seller', 'password': 'SellerPass1'
        }), content_type='application/json')
        self.seller_token = res.json()['access']
        res = self.client.post('/api/auth/login/', json.dumps({
            'username': 'buyer', 'password': 'BuyerPass1'
        }), content_type='application/json')
        self.buyer_token = res.json()['access']

    def test_list_products_public(self):
        res = self.client.get('/api/products/')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()), 1)

    def test_product_detail(self):
        res = self.client.get(f'/api/products/{self.product.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['name'], 'Test Snake')

    def test_create_listing_requires_auth(self):
        res = self.client.post('/api/products/create/', json.dumps({
            'name': 'Unauthorized', 'price': 10, 'description': 'X', 'condition': 'New'
        }), content_type='application/json')
        self.assertEqual(res.status_code, 401)

    def test_create_listing_authenticated(self):
        res = self.client.post('/api/products/create/', json.dumps({
            'name': 'New Listing', 'price': '25.00',
            'description': 'Fresh item', 'condition': 'New'
        }), content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.seller_token}')
        self.assertEqual(res.status_code, 201)

    def test_search_products(self):
        res = self.client.get('/api/products/?q=Snake')
        self.assertEqual(res.status_code, 200)
        results = res.json()
        self.assertTrue(any('Snake' in p['name'] for p in results))

    def test_delete_own_listing(self):
        res = self.client.delete(
            f'/api/products/{self.product.id}/manage/',
            HTTP_AUTHORIZATION=f'Bearer {self.seller_token}'
        )
        self.assertEqual(res.status_code, 204)

    def test_delete_others_listing_forbidden(self):
        res = self.client.delete(
            f'/api/products/{self.product.id}/manage/',
            HTTP_AUTHORIZATION=f'Bearer {self.buyer_token}'
        )
        self.assertEqual(res.status_code, 403)

    def test_filter_by_condition(self):
        res = self.client.get('/api/products/?condition=New')
        self.assertEqual(res.status_code, 200)
        for p in res.json():
            self.assertEqual(p['condition'], 'New')


class AdminAPITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'AdminPass1')
        self.regular = User.objects.create_user('regular', 'reg@example.com', 'RegPass123')
        res = self.client.post('/api/auth/login/', json.dumps({
            'username': 'admin', 'password': 'AdminPass1'
        }), content_type='application/json')
        self.admin_token = res.json()['access']
        res = self.client.post('/api/auth/login/', json.dumps({
            'username': 'regular', 'password': 'RegPass123'
        }), content_type='application/json')
        self.regular_token = res.json()['access']

    def test_admin_stats_accessible_by_admin(self):
        res = self.client.get('/api/admin/stats/', HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        self.assertEqual(res.status_code, 200)
        self.assertIn('total_users', res.json())

    def test_admin_stats_blocked_for_regular_user(self):
        res = self.client.get('/api/admin/stats/', HTTP_AUTHORIZATION=f'Bearer {self.regular_token}')
        self.assertEqual(res.status_code, 403)

    def test_admin_user_list(self):
        res = self.client.get('/api/admin/users/', HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()), 2)


class RateLimitTests(TestCase):
    def test_rate_limit_returns_429(self):
        """Spam 200 requests — should hit 429 before completing all."""
        hit_429 = False
        for _ in range(120):
            res = self.client.get('/api/products/')
            if res.status_code == 429:
                hit_429 = True
                break
        self.assertTrue(hit_429, 'Rate limit should have triggered at 100 requests')
