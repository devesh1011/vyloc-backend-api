"""
Dodo Payments Integration Router

Handles:
1. Creating checkout sessions for subscription plans
2. Processing webhook events from Dodo Payments
3. Managing subscription status updates
"""

import os
import hmac
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header, Depends
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client

# Try to import Dodo Payments SDK
try:
    from dodopayments import DodoPayments
    DODO_SDK_AVAILABLE = True
except ImportError:
    DODO_SDK_AVAILABLE = False
    print("Warning: dodopayments SDK not installed. Install with: pip install dodopayments")

router = APIRouter(prefix="/payments", tags=["payments"])

# Environment variables
DODO_API_KEY = os.getenv("DODO_PAYMENTS_API_KEY")
DODO_WEBHOOK_SECRET = os.getenv("DODO_PAYMENTS_WEBHOOK_KEY")
DODO_ENVIRONMENT = os.getenv("DODO_PAYMENTS_ENVIRONMENT", "test_mode")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Anon key for basic operations
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Service role key for admin operations
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Initialize Supabase client with service role key for admin operations (webhooks)
def get_supabase_admin() -> Client:
    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Supabase URL not configured")
    # Try service key first, fallback to anon key
    key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
    if not key:
        raise HTTPException(status_code=500, detail="Supabase key not configured")
    return create_client(SUPABASE_URL, key)

# Initialize Dodo Payments client
def get_dodo_client() -> Optional[DodoPayments]:
    if not DODO_SDK_AVAILABLE:
        return None
    if not DODO_API_KEY:
        raise HTTPException(status_code=500, detail="Dodo Payments API key not configured")
    return DodoPayments(
        bearer_token=DODO_API_KEY,
        environment=DODO_ENVIRONMENT,
    )


# Product IDs mapped to tiers (you'll need to create these in Dodo Payments dashboard)
TIER_PRODUCTS = {
    "starter": {
        "product_id": os.getenv("DODO_PRODUCT_STARTER", "prod_starter"),
        "price": 2900,  # $29.00 in cents
        "credits": 100,
    },
    "pro": {
        "product_id": os.getenv("DODO_PRODUCT_PRO", "prod_pro"),
        "price": 9900,  # $99.00 in cents
        "credits": 500,
    },
    "enterprise": {
        "product_id": os.getenv("DODO_PRODUCT_ENTERPRISE", "prod_enterprise"),
        "price": 49900,  # $499.00 in cents
        "credits": 3000,
    },
}


class CheckoutRequest(BaseModel):
    tier: str
    user_id: str
    email: EmailStr


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class WebhookPayload(BaseModel):
    business_id: str
    type: str
    timestamp: str
    data: dict


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(request: CheckoutRequest):
    """
    Create a Dodo Payments checkout session for subscription upgrade.
    
    This endpoint:
    1. Validates the requested tier
    2. Creates a checkout session with Dodo Payments
    3. Returns the checkout URL for frontend redirect
    """
    # Validate tier
    if request.tier not in TIER_PRODUCTS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid tier: {request.tier}. Valid tiers: {list(TIER_PRODUCTS.keys())}"
        )
    
    tier_config = TIER_PRODUCTS[request.tier]
    
    # Get Dodo client
    dodo = get_dodo_client()
    if not dodo:
        raise HTTPException(status_code=500, detail="Payment service not available")
    
    try:
        # Create checkout session with Dodo Payments
        session = dodo.checkout_sessions.create(
            product_cart=[
                {
                    "product_id": tier_config["product_id"],
                    "quantity": 1
                }
            ],
            # Pass user info as metadata for webhook processing
            metadata={
                "user_id": request.user_id,
                "tier": request.tier,
                "credits": str(tier_config["credits"]),
            },
            # Return URLs
            return_url=f"{FRONTEND_URL}/dashboard?payment=success",
            # Customer info
            customer={
                "email": request.email,
            }
        )
        
        return CheckoutResponse(
            checkout_url=session.checkout_url,
            session_id=session.session_id
        )
        
    except Exception as e:
        import traceback
        print(f"Error creating checkout session: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")


def verify_webhook_signature(payload: bytes, headers: dict) -> bool:
    """
    Verify Dodo Payments webhook signature using Standard Webhooks spec.
    
    The signature is computed as:
    HMAC-SHA256(webhook-id + "." + webhook-timestamp + "." + payload, secret)
    """
    if not DODO_WEBHOOK_SECRET:
        print("Warning: Webhook secret not configured")
        return False
    
    webhook_id = headers.get("webhook-id")
    webhook_timestamp = headers.get("webhook-timestamp")
    webhook_signature = headers.get("webhook-signature")
    
    if not all([webhook_id, webhook_timestamp, webhook_signature]):
        return False
    
    # Build signed message
    signed_payload = f"{webhook_id}.{webhook_timestamp}.{payload.decode('utf-8')}"
    
    # Compute expected signature
    # The secret may be base64 encoded with a prefix like "whsec_"
    secret = DODO_WEBHOOK_SECRET
    if secret.startswith("whsec_"):
        import base64
        secret = base64.b64decode(secret[6:])
    else:
        secret = secret.encode('utf-8')
    
    expected_signature = hmac.new(
        secret,
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    import base64
    expected_b64 = base64.b64encode(expected_signature).decode('utf-8')
    
    # The signature header may contain multiple signatures (for rotation)
    # Format: "v1,<base64-signature> v1,<base64-signature>"
    for sig_part in webhook_signature.split(" "):
        if "," in sig_part:
            version, sig = sig_part.split(",", 1)
            if version == "v1" and hmac.compare_digest(sig, expected_b64):
                return True
    
    return False


async def is_webhook_processed(supabase: Client, webhook_id: str) -> bool:
    """Check if a webhook has already been processed (database-based idempotency)."""
    try:
        result = supabase.table("payment_webhook_events").select("id").eq("webhook_id", webhook_id).execute()
        return len(result.data) > 0
    except Exception:
        return False


async def store_webhook_event(supabase: Client, webhook_id: str, event_type: str, payload: dict):
    """Store processed webhook event for audit trail."""
    try:
        supabase.table("payment_webhook_events").insert({
            "webhook_id": webhook_id,
            "event_type": event_type,
            "payload": payload,
        }).execute()
    except Exception as e:
        print(f"Error storing webhook event: {e}")


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    webhook_id: str = Header(None, alias="webhook-id"),
    webhook_signature: str = Header(None, alias="webhook-signature"),
    webhook_timestamp: str = Header(None, alias="webhook-timestamp"),
):
    """
    Handle incoming webhooks from Dodo Payments.
    
    Security measures:
    1. Verify webhook signature
    2. Check for duplicate webhook IDs (idempotency)
    3. Process asynchronously and respond immediately
    
    Supported events:
    - payment.succeeded: Update subscription after successful payment
    - payment.failed: Handle failed payment
    - subscription.created: New subscription created
    - subscription.cancelled: Subscription cancelled
    """
    print(f"\n{'='*80}")
    print("WEBHOOK ENDPOINT HIT!")
    print(f"Webhook ID header: {webhook_id}")
    print(f"Headers received: {dict(request.headers)}")
    print(f"{'='*80}\n")
    
    # Get raw payload
    payload = await request.body()
    
    # Verify signature
    headers = {
        "webhook-id": webhook_id,
        "webhook-timestamp": webhook_timestamp,
        "webhook-signature": webhook_signature,
    }
    
    if not verify_webhook_signature(payload, headers):
        print("❌ Webhook signature verification failed!")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    print("✅ Webhook signature verified")
    
    # Get supabase client for idempotency check
    supabase = get_supabase_admin()
    
    # Idempotency check using database
    if await is_webhook_processed(supabase, webhook_id):
        return {"received": True, "status": "already_processed"}
    
    # Parse payload
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    event_type = data.get("type")
    event_data = data.get("data", {})
    
    print(f"\n{'='*60}")
    print(f"WEBHOOK RECEIVED: {event_type}")
    print(f"Webhook ID: {webhook_id}")
    print("Full Payload:")
    print(json.dumps(data, indent=2))
    print(f"{'='*60}\n")
    
    # Store webhook event for idempotency and audit trail
    await store_webhook_event(supabase, webhook_id, event_type, data)
    
    # Process the event
    try:
        if event_type == "payment.succeeded":
            await handle_payment_succeeded(event_data)
        elif event_type == "payment.failed":
            await handle_payment_failed(event_data)
        elif event_type == "subscription.created":
            await handle_subscription_created(event_data)
        elif event_type == "subscription.cancelled":
            await handle_subscription_cancelled(event_data)
        elif event_type == "subscription.renewed":
            await handle_subscription_renewed(event_data)
        else:
            print(f"Unhandled event type: {event_type}")
    except Exception as e:
        print(f"Error processing webhook {event_type}: {e}")
        # Still return 200 to acknowledge receipt
    
    return {"received": True}


async def handle_payment_succeeded(event_data: dict):
    """Handle successful payment - activate/upgrade subscription."""
    supabase = get_supabase_admin()
    
    # Extract metadata
    metadata = event_data.get("metadata", {})
    user_id = metadata.get("user_id")
    tier = metadata.get("tier")
    credits = int(metadata.get("credits", 0))
    
    if not user_id or not tier:
        print("Missing user_id or tier in payment metadata")
        return
    
    payment_id = event_data.get("payment_id")
    subscription_id = event_data.get("subscription_id", f"sub_{payment_id}")
    
    # Check for existing subscription
    existing = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").execute()
    
    if existing.data:
        # Update existing subscription
        supabase.table("subscriptions").update({
            "tier": tier,
            "dodo_subscription_id": subscription_id,
            "dodo_payment_id": payment_id,
            "monthly_credit_limit": credits,
            "credits_used": 0,  # Reset credits on upgrade
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", existing.data[0]["id"]).execute()
        print(f"Updated subscription for user {user_id} to {tier}")
    else:
        # Create new subscription
        supabase.table("subscriptions").insert({
            "user_id": user_id,
            "polar_subscription_id": subscription_id,  # Using existing column
            "polar_product_id": tier,  # Using existing column
            "tier": tier,
            "status": "active",
            "monthly_credit_limit": credits,
            "credits_used": 0,
        }).execute()
        print(f"Created new {tier} subscription for user {user_id}")


async def handle_payment_failed(event_data: dict):
    """Handle failed payment - notify user or mark subscription at risk."""
    metadata = event_data.get("metadata", {})
    user_id = metadata.get("user_id")
    
    if not user_id:
        return
    
    supabase = get_supabase_admin()
    
    # Update subscription status to past_due
    supabase.table("subscriptions").update({
        "status": "past_due",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", user_id).eq("status", "active").execute()
    
    print(f"Marked subscription past_due for user {user_id}")


async def handle_subscription_created(event_data: dict):
    """Handle new subscription creation."""
    # This is often handled by payment.succeeded, but included for completeness
    print(f"Subscription created: {event_data.get('subscription_id')}")


async def handle_subscription_cancelled(event_data: dict):
    """Handle subscription cancellation."""
    supabase = get_supabase_admin()
    
    subscription_id = event_data.get("subscription_id")
    
    if subscription_id:
        # Find and cancel subscription
        result = supabase.table("subscriptions").update({
            "status": "canceled",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("polar_subscription_id", subscription_id).execute()
        
        print(f"Cancelled subscription: {subscription_id}")


async def handle_subscription_renewed(event_data: dict):
    """Handle subscription renewal - reset credits."""
    supabase = get_supabase_admin()
    
    subscription_id = event_data.get("subscription_id")
    
    if subscription_id:
        # Reset credits for the new billing period
        supabase.table("subscriptions").update({
            "credits_used": 0,
            "current_period_start": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("polar_subscription_id", subscription_id).eq("status", "active").execute()
        
        print(f"Renewed subscription: {subscription_id}")


@router.get("/subscription/{user_id}")
async def get_user_subscription(user_id: str):
    """Get the current subscription for a user."""
    supabase = get_supabase_admin()
    
    result = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").single().execute()
    
    if not result.data:
        return {"tier": "free", "credits_remaining": 5}
    
    sub = result.data
    credits_remaining = sub.get("monthly_credit_limit", 0) - sub.get("credits_used", 0)
    
    return {
        "tier": sub.get("tier"),
        "status": sub.get("status"),
        "credits_remaining": credits_remaining,
        "monthly_limit": sub.get("monthly_credit_limit"),
    }


@router.get("/subscription-status/{subscription_id}")
async def check_subscription_from_dodo(subscription_id: str):
    """
    Check subscription status directly from Dodo Payments.
    Useful for checking if payment/subscription has been processed.
    """
    dodo = get_dodo_client()
    if not dodo:
        raise HTTPException(status_code=500, detail="Payment service not available")
    
    try:
        # Retrieve subscription from Dodo
        subscription = dodo.subscriptions.retrieve(subscription_id)
        
        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "customer_id": getattr(subscription, 'customer_id', None),
            "product_id": getattr(subscription, 'product_id', None),
            "created_at": getattr(subscription, 'created_at', None),
        }
    except Exception as e:
        print(f"Error retrieving subscription from Dodo: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve subscription: {str(e)}")
