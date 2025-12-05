import requests
import json
import logging
from django.conf import settings
from datetime import datetime
import uuid
import time

logger = logging.getLogger(__name__)
payment_logger = logging.getLogger("payment")


class STKPushAPI:
    @staticmethod
    def normalize_phone_number(phone_number: str) -> str:
        phone_number = str(phone_number).strip()

        if phone_number.startswith("+"):
            phone_number = phone_number[1:]

        if phone_number.startswith("0"):
            phone_number = "254" + phone_number[1:]
        elif phone_number.startswith("7") or phone_number.startswith("1"):
            phone_number = "254" + phone_number
        elif not phone_number.startswith("254"):
            phone_number = "254" + phone_number

        return phone_number

    @staticmethod
    def initiate_stk_push(
        phone_number, amount, reference, purpose="sale", callback_url=None
    ):
        try:
            logger.critical(
                f"INITIATING STK PUSH - Purpose: {purpose}, Phone: {phone_number}, "
                f"Amount: {amount}, Reference: {reference}"
            )

            phone_number = STKPushAPI.normalize_phone_number(phone_number)

            if getattr(settings, "USE_MOCK_STK_PUSH", False):
                logger.critical("Using mock STK Push API in development/testing mode")
                return STKPushAPI._mock_stk_push(
                    phone_number, amount, reference, purpose
                )

            api_key = settings.HASHPAY_API_KEY
            account_id = settings.HASHPAY_ACCOUNT_ID
            api_url = "https://api.hashback.co.ke/initiatestk"

            amount_int = int(float(amount))

            if amount_int <= 0:
                logger.error(f"Invalid amount: {amount} converted to {amount_int}")
                return {
                    "success": False,
                    "message": "Invalid amount. Amount must be greater than 0.",
                    "data": {},
                }

            payload = {
                "api_key": api_key,
                "account_id": account_id,
                "amount": str(amount_int),
                "msisdn": phone_number,
                "reference": reference,
            }

            logger.info(f"Making API request to HashPay: {api_url}")
            logger.info(f"Payload: {payload}")

            response = requests.post(
                api_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            logger.info(f"Response Status Code: {response.status_code}")
            logger.info(f"Response Text: {response.text}")

            if response.status_code in [200, 201, 202]:
                result = response.json()
                logger.info(f"HashPay API SUCCESS - {result}")

                response_code = str(result.get("ResponseCode", ""))
                checkout_id = result.get("CheckoutRequestID", "")
                merchant_request_id = result.get("MerchantRequestID", "")

                if response_code == "0" and checkout_id:
                    return {
                        "success": True,
                        "message": "STK Push initiated successfully",
                        "data": {
                            "external_reference": reference,
                            "checkout_request_id": checkout_id,
                            "merchant_request_id": merchant_request_id,
                            "status": "PENDING",
                            "phone_number": phone_number,
                            "amount": float(amount),
                            "reference": reference,
                            "purpose": purpose,
                            "response_description": result.get(
                                "ResponseDescription", ""
                            ),
                        },
                    }
                else:
                    logger.error(f"HashPay returned error: {result}")
                    return {
                        "success": False,
                        "message": result.get(
                            "ResponseDescription",
                            result.get("errorMessage", "Failed to initiate STK Push"),
                        ),
                        "data": {},
                    }
            else:
                logger.error(
                    f"STK Push FAILED - Status: {response.status_code}, Response: {response.text}"
                )
                return {
                    "success": False,
                    "message": f"Failed to initiate STK Push: {response.status_code}",
                    "data": {},
                }
        except Exception as e:
            logger.error(f"STK Push ERROR - Phone: {phone_number}, Error: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}", "data": {}}

    @staticmethod
    def check_transaction_status(checkout_id):
        try:
            api_key = settings.HASHPAY_API_KEY
            account_id = settings.HASHPAY_ACCOUNT_ID
            api_url = "https://api.hashback.co.ke/transactionstatus"

            payload = {
                "api_key": api_key,
                "account_id": account_id,
                "checkoutid": checkout_id,
            }

            logger.info(f"Checking transaction status for checkout_id: {checkout_id}")

            response = requests.post(
                api_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Transaction status response: {result}")

                result_code = str(result.get("ResultCode", ""))

                PENDING_CODES = ["4999", "1032", "1"]
                FAILED_CODES = ["1037", "1", "17", "26", "2001"]

                is_complete = result_code == "0"
                is_pending = result_code in PENDING_CODES
                is_failed = result_code in FAILED_CODES and not is_pending

                return {
                    "success": True,
                    "data": result,
                    "is_complete": is_complete,
                    "is_pending": is_pending,
                    "is_failed": is_failed,
                }
            else:
                logger.error(f"Status check failed: {response.status_code}")
                return {
                    "success": False,
                    "message": "Failed to check transaction status",
                }
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}

    @staticmethod
    def _mock_stk_push(phone_number, amount, reference, purpose="sale"):
        transaction_id = f"TRX-{uuid.uuid4().hex[:8].upper()}"

        logger.info(
            f"MOCK STK Push - Purpose: {purpose}, Phone: {phone_number}, "
            f"Amount: {amount}, Reference: {reference}"
        )

        time.sleep(0.5)

        mock_response = {
            "success": True,
            "message": "MOCK: STK Push initiated successfully",
            "data": {
                "external_reference": reference,
                "checkout_request_id": f"ws_CO_{uuid.uuid4().hex[:10]}",
                "merchant_request_id": f"MOCK-MR-{uuid.uuid4().hex[:8]}",
                "status": "PENDING",
                "phone_number": phone_number,
                "amount": float(amount),
                "reference": reference,
                "purpose": purpose,
                "timestamp": datetime.now().isoformat(),
            },
        }

        logger.info(f"MOCK STK Push RESPONSE - External Reference: {reference}")
        return mock_response
