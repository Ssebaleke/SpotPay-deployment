from django.core.management.base import BaseCommand
from payments.live_client import LivePayClient
import json

class Command(BaseCommand):
    help = 'Test different LivePay credential combinations'

    def handle(self, *args, **options):
        key_id = "89b4e8e5858ada4e"
        api_key = "39eacb226cb2466f16c243bab671897ba3288f9b82a1639ff8e0df9df2503c96"
        
        self.stdout.write("Testing LivePay Credential Combinations")
        self.stdout.write("=" * 50)
        
        # Test 1: Current setup (Key ID as public_key, API key as secret_key)
        self.stdout.write("\n1. Testing: Key ID as public_key, API key as secret_key")
        try:
            client = LivePayClient(public_key=key_id, secret_key=api_key)
            result = client.collect(amount=1000, phone="256700000000", reference="TEST1", description="Test 1")
            self.stdout.write(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            self.stdout.write(f"Error: {e}")
        
        # Test 2: Swapped (API key as public_key, Key ID as secret_key)
        self.stdout.write("\n2. Testing: API key as public_key, Key ID as secret_key")
        try:
            client = LivePayClient(public_key=api_key, secret_key=key_id)
            result = client.collect(amount=1000, phone="256700000000", reference="TEST2", description="Test 2")
            self.stdout.write(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            self.stdout.write(f"Error: {e}")
        
        # Test 3: Same key for both
        self.stdout.write("\n3. Testing: API key for both fields")
        try:
            client = LivePayClient(public_key=api_key, secret_key=api_key)
            result = client.collect(amount=1000, phone="256700000000", reference="TEST3", description="Test 3")
            self.stdout.write(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            self.stdout.write(f"Error: {e}")
        
        # Test 4: Key ID for both
        self.stdout.write("\n4. Testing: Key ID for both fields")
        try:
            client = LivePayClient(public_key=key_id, secret_key=key_id)
            result = client.collect(amount=1000, phone="256700000000", reference="TEST4", description="Test 4")
            self.stdout.write(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            self.stdout.write(f"Error: {e}")
        
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Check which test gives a successful response or different error message.")