from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from django.db import models
from apps.customers.models import Customer
from apps.verification.utils import verify_email, verify_phone, verify_pan, log_verification_attempt
import logging

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_customer_data(request):
    customer_id = request.data.get("customer_id")
    verify_type = request.data.get("type")
    value = request.data.get("value")

    if not all([customer_id, verify_type, value]):
        return Response(
            {"error": "Missing required fields: customer_id, type, value"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    if verify_type not in ["email", "phone", "pan"]:
        return Response(
            {"error": "Invalid verification type. Must be 'email', 'phone', or 'pan'"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response(
            {"error": "Customer not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )

    result = {"verified": False, "message": "Verification not performed"}

    if verify_type == "email":
        if value != customer.email:
            result = {
                "verified": False,
                "message": "Email does not match customer's registered email"
            }
        else:
            if customer.email_verified:
                result = {
                    "verified": True,
                    "message": "Email already verified",
                    "already_verified": True,
                    "verified_at": customer.email_verified_at.isoformat() if customer.email_verified_at else None
                }
            else:
                customer_name = f"{customer.first_name} {customer.last_name}".strip()
                result = verify_email(customer_name, value)

        customer.email_verified = result["verified"]
        if result["verified"] and not result.get("already_verified"):
            customer.email_verified_at = timezone.now()
        elif not result["verified"]:
            customer.email_verified_at = None

    elif verify_type == "phone":
        def normalize_phone_number(phone):
            """Normalize phone number by removing + and country code for comparison"""
            phone = phone.strip()
            if phone.startswith('+'):
                phone = phone[1:]
            if phone.startswith('91') and len(phone) > 10:
                phone = phone[2:]
            return phone
        
        normalized_value = normalize_phone_number(value)
        normalized_customer_phone = normalize_phone_number(customer.phone)
        
        if normalized_value != normalized_customer_phone:
            result = {
                "verified": False,
                "message": f"Phone number does not match customer's registered number."
            }
        else:
            if customer.phone_verified:
                result = {
                    "verified": True,
                    "message": "Phone number already verified",
                    "already_verified": True,
                    "verified_at": customer.phone_verified_at.isoformat() if customer.phone_verified_at else None
                }
            else:
                result = verify_phone(value)

        customer.phone_verified = result["verified"]
        if result["verified"] and not result.get("already_verified"):
            customer.phone_verified_at = timezone.now()
        elif not result["verified"]:
            customer.phone_verified_at = None

    elif verify_type == "pan":
        if value != customer.pan_number:
            result = {
                "verified": False,
                "message": "PAN number does not match customer's registered PAN"
            }
        else:
            if customer.pan_verified:
                result = {
                    "verified": True,
                    "message": "PAN number already verified",
                    "already_verified": True,
                    "verified_at": customer.pan_verified_at.isoformat() if customer.pan_verified_at else None
                }
            else:
                result = verify_pan(value)

        customer.pan_verified = result["verified"]
        if result["verified"] and not result.get("already_verified"):
            customer.pan_verified_at = timezone.now()
            customer.pan_number = value
        elif not result["verified"]:
            customer.pan_verified_at = None

    update_fields = []
    if verify_type == "email":
        update_fields.extend(['email_verified', 'email_verified_at'])
    elif verify_type == "phone":
        update_fields.extend(['phone_verified', 'phone_verified_at'])
    elif verify_type == "pan":
        update_fields.extend(['pan_verified', 'pan_verified_at', 'pan_number'])

    customer.save(update_fields=update_fields)

    log_verification_attempt(customer_id, verify_type, value, result)

    response_data = {
        "customer_id": customer.id,
        "type": verify_type,
        "verified": result["verified"],
        "message": result["message"],
    }
    
    if result.get("already_verified"):
        response_data["verified_at"] = result.get("verified_at")
        response_data["already_verified"] = True
    else:
        response_data["verified_at"] = timezone.now().isoformat() if result["verified"] else None
    
    return Response(response_data, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_customer_verification_status(request, customer_id):
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response(
            {"error": "Customer not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        "customer_id": customer.id,
        "customer_name": customer.full_name,
        "verification_status": {
            "email": {
                "verified": customer.email_verified,
                "verified_at": customer.email_verified_at.isoformat() if customer.email_verified_at else None,
                "email": customer.email
            },
            "phone": {
                "verified": customer.phone_verified,
                "verified_at": customer.phone_verified_at.isoformat() if customer.phone_verified_at else None,
                "phone": customer.phone
            },
            "pan": {
                "verified": customer.pan_verified,
                "verified_at": customer.pan_verified_at.isoformat() if customer.pan_verified_at else None,
                "pan_number": customer.pan_number
            }
        }
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_verify_customers(request):
    customer_ids = request.data.get("customer_ids", [])
    verify_type = request.data.get("type")

    if not customer_ids or not verify_type:
        return Response(
            {"error": "Missing required fields: customer_ids, type"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    if verify_type not in ["email", "phone", "pan"]:
        return Response(
            {"error": "Invalid verification type. Must be 'email', 'phone', or 'pan'"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    results = []
    
    for customer_id in customer_ids:
        try:
            customer = Customer.objects.get(id=customer_id)
            
            if verify_type == "email":
                customer_name = f"{customer.first_name} {customer.last_name}".strip()
                result = verify_email(customer_name, customer.email)
                
                customer.email_verified = result["verified"]
                if result["verified"]:
                    customer.email_verified_at = timezone.now()
                else:
                    customer.email_verified_at = None
                customer.save(update_fields=['email_verified', 'email_verified_at'])
                
            elif verify_type == "phone":
                result = verify_phone(customer.phone)
                
                customer.phone_verified = result["verified"]
                if result["verified"]:
                    customer.phone_verified_at = timezone.now()
                else:
                    customer.phone_verified_at = None
                customer.save(update_fields=['phone_verified', 'phone_verified_at'])
                
            elif verify_type == "pan" and customer.pan_number:
                result = verify_pan(customer.pan_number)
                
                customer.pan_verified = result["verified"]
                if result["verified"]:
                    customer.pan_verified_at = timezone.now()
                else:
                    customer.pan_verified_at = None
                customer.save(update_fields=['pan_verified', 'pan_verified_at'])
            else:
                result = {"verified": False, "message": "PAN number not available for verification"}

            results.append({
                "customer_id": customer.id,
                "customer_name": customer.full_name,
                "verified": result["verified"],
                "message": result["message"]
            })
            
            log_verification_attempt(customer_id, verify_type, 
                                   getattr(customer, verify_type == "pan" and "pan_number" or verify_type), 
                                   result)
            
        except Customer.DoesNotExist:
            results.append({
                "customer_id": customer_id,
                "customer_name": None,
                "verified": False,
                "message": "Customer not found"
            })

    return Response({
        "type": verify_type,
        "total_processed": len(customer_ids),
        "results": results
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_pan_with_document(request):
    customer_id = request.data.get("customer_id")
    
    if not customer_id:
        return Response(
            {"error": "Missing required field: customer_id"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return Response(
            {"error": "Customer not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if customer.pan_verified:
        return Response({
            "customer_id": customer.id,
            "pan_number": customer.pan_number,
            "verified": True,
            "message": "PAN already verified",
            "verified_at": customer.pan_verified_at.isoformat() if customer.pan_verified_at else None,
            "already_verified": True
        }, status=status.HTTP_200_OK)
    
    try:
        from apps.customers_files.models import CustomerFile
        
        customer_file = CustomerFile.objects.filter(
            customer=customer,
            is_active=True,
            pan_number__isnull=False
        ).exclude(pan_number='').order_by('-uploaded_at').first()
        
        if not customer_file:
            if customer.pan_number and customer.pan_number.strip():
                pan_number = customer.pan_number
                logger.info(f"Using PAN number from customer record: {pan_number}")
            else:
                return Response({
                    "error": "PAN number not found",
                    "message": "Please upload a PAN card image first. PAN will be extracted automatically during upload.",
                    "customer_id": customer.id
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            pan_number = customer_file.pan_number
            logger.info(f"Found PAN number in customer_files table: {pan_number} (File: {customer_file.file_name})")
            
            if not customer.pan_number or customer.pan_number != pan_number:
                customer.pan_number = pan_number
                customer.save(update_fields=['pan_number'])
                logger.info(f"Updated customer {customer_id} PAN number from file")
        
    except Exception as e:
        logger.error(f"Error fetching PAN from customer_files: {str(e)}")
        return Response({
            "error": "Error accessing customer files",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        logger.info(f"Verifying PAN {pan_number} for customer {customer_id} via Bureau API...")
        
        verification_result = verify_pan(pan_number)
        
        customer.pan_verified = verification_result["verified"]
        if verification_result["verified"]:
            customer.pan_verified_at = timezone.now()
        else:
            customer.pan_verified_at = None
        
        customer.save(update_fields=['pan_verified', 'pan_verified_at'])
        
        log_verification_attempt(
            customer_id,
            'pan',
            pan_number,
            verification_result
        )
        
        response_data = {
            "customer_id": customer.id,
            "pan_number": pan_number,
            "verified": verification_result["verified"],
            "message": verification_result["message"],
            "verified_at": customer.pan_verified_at.isoformat() if customer.pan_verified_at else None
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error during Bureau API verification: {str(e)}", exc_info=True)
        return Response({
            "error": "Error during verification",
            "message": f"Failed to verify PAN: {str(e)}",
            "customer_id": customer.id
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
