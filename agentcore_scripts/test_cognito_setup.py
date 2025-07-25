#!/usr/bin/env python3
"""
Test script for the modified setup_cognito_user_pool_with_signup function.
This script demonstrates the usage of the updated function.
"""

import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import setup_cognito_user_pool_with_signup

def test_cognito_setup():
    """
    Test the modified setup_cognito_user_pool_with_signup function.
    This will either create a new pool or update an existing one.
    """
    print("🧪 Testing Cognito User Pool setup with signup...")
    print("=" * 50)
    
    try:
        # Test with default pool name
        result = setup_cognito_user_pool_with_signup()
        
        if result:
            print("\n🎉 Success! Cognito setup completed.")
            print("📋 Results:")
            for key, value in result.items():
                if 'secret' in key.lower():
                    print(f"   {key}: {'*' * 20}")
                else:
                    print(f"   {key}: {value}")
        else:
            print("\n❌ Setup failed - check the logs above for details.")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_cognito_setup_custom_name():
    """
    Test the function with a custom pool name.
    """
    print("\n🧪 Testing Cognito User Pool setup with custom name...")
    print("=" * 50)
    
    custom_pool_name = "TestStrandDemoPoolWithSignup"
    
    try:
        result = setup_cognito_user_pool_with_signup(pool_name=custom_pool_name)
        
        if result:
            print(f"\n🎉 Success! Custom Cognito pool '{custom_pool_name}' setup completed.")
            print("📋 Results:")
            for key, value in result.items():
                if 'secret' in key.lower():
                    print(f"   {key}: {'*' * 20}")
                else:
                    print(f"   {key}: {value}")
        else:
            print(f"\n❌ Setup failed for custom pool '{custom_pool_name}' - check the logs above.")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting Cognito User Pool Setup Tests")
    print("=" * 60)
    
    # Test 1: Default setup
    success1 = test_cognito_setup()
    
    # Test 2: Custom pool name setup
    success2 = test_cognito_setup_custom_name()
    
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   Default pool test: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"   Custom pool test:  {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    if success1 and success2:
        print("\n🎉 All tests passed! The modified function handles existing pools correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the error messages above.")
        sys.exit(1)