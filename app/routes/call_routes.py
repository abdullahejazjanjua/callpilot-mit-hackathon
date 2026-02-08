import logging

from fastapi import APIRouter, Query, Request, Response, WebSocket
from pydantic import BaseModel, Field

from app.tools.call_tool import ACTIVE_CALLS, initiate_call

logger = logging.getLogger("callpilot.routes.call")

router = APIRouter(prefix="/call", tags=["Phone Calls (Simulated)"])

CALL_INTEGRATION_STATUS = "Simulated (no Twilio)"


class CallOutboundRequest(BaseModel):
    provider_phone: str
    provider_name: str
    appointment_time: str
    service_type: str = "appointment"
    patient_name: str = "CallPilot User"


@router.post("/outbound")
async def call_outbound(request: CallOutboundRequest):
    logger.info(f"[CALL] Simulating outbound call to {request.provider_name} at {request.provider_phone}...")

    result = initiate_call(
        provider_phone=request.provider_phone,
        provider_name=request.provider_name,
        appointment_time=request.appointment_time,
        service_type=request.service_type,
        patient_name=request.patient_name,
    )

    if result.get("success"):
        logger.info(f"[CALL] Simulated call completed: {result['call_sid']}")
    else:
        logger.warning(f"[CALL] Simulated call issue: {result.get('message')}")

    return result


@router.post("/twiml")
async def twiml_webhook(
    request: Request,
    provider_name: str = Query("the clinic"),
    appointment_time: str = Query(""),
    patient_name: str = Query("the patient"),
    service_type: str = Query("appointment"),
    date: str = Query(""),
    call_type: str = Query("inquiry"),
):
    logger.info(f"[TWIML] Legacy endpoint hit for {provider_name} ({call_type}) — calls are simulated")
    return Response(
        content=(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Say>Calls are currently simulated. No live connection.</Say></Response>'
        ),
        media_type="application/xml",
    )


@router.websocket("/media-stream")
async def media_stream_websocket(
    websocket: WebSocket,
    provider_name: str = Query("the clinic"),
    appointment_time: str = Query(""),
    patient_name: str = Query("the patient"),
    service_type: str = Query("appointment"),
    date: str = Query(""),
    call_type: str = Query("inquiry"),
):
    await websocket.accept()
    logger.info(f"[MEDIA STREAM] Legacy WebSocket hit for {provider_name} — calls are simulated, closing.")
    await websocket.close(code=1000, reason="Calls are simulated. No media stream needed.")


@router.post("/status")
async def call_status_webhook(request: Request):
    form_data = await request.form()

    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")
    duration = form_data.get("CallDuration", "0")

    logger.info(f"[CALL STATUS] Call {call_sid[:16]}... -> {call_status} (duration: {duration}s)")

    if call_sid in ACTIVE_CALLS:
        ACTIVE_CALLS[call_sid]["status"] = call_status
        if duration != "0":
            ACTIVE_CALLS[call_sid]["duration"] = duration

    return {"status": "received"}


@router.get("/active")
async def list_active_calls():
    return {
        "calls": list(ACTIVE_CALLS.values()),
        "total": len(ACTIVE_CALLS),
        "mode": "simulated",
    }


@router.get("/status/{call_sid}")
async def get_single_call_status(call_sid: str):
    if call_sid in ACTIVE_CALLS:
        call = ACTIVE_CALLS[call_sid]
        return {
            "success": True,
            "call_sid": call_sid,
            "status": call.get("status", "unknown"),
            "duration": call.get("duration", "0"),
            "to": call.get("to", ""),
            "from_": call.get("from", "+1-CALLPILOT"),
            "simulated": True,
        }

    return {
        "success": False,
        "message": f"Call {call_sid} not found in active calls.",
    }
