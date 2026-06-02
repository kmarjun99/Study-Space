from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models.inquiry import Inquiry, InquiryStatus, InquiryType
from app.models.accommodation import Accommodation
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/inquiries", tags=["inquiries"])

# --- Schemas ---
class InquiryCreate(BaseModel):
    accommodation_id: str
    type: InquiryType = InquiryType.QUESTION
    question: str
    student_name: str
    student_phone: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None

class InquiryReply(BaseModel):
    reply: str

class InquiryResponse(BaseModel):
    id: str
    accommodation_id: str
    student_id: str
    owner_id: str
    type: str
    question: str
    student_name: str
    student_phone: Optional[str]
    preferred_date: Optional[str]
    preferred_time: Optional[str]
    reply: Optional[str]
    status: str
    created_at: datetime
    replied_at: Optional[datetime]
    # Joined data
    accommodation_name: Optional[str] = None
    
    class Config:
        from_attributes = True


# --- Endpoints ---

@router.post("/", response_model=InquiryResponse)
async def create_inquiry(
    data: InquiryCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new inquiry (question or visit request) from a student to an accommodation owner."""
    # Get accommodation to find owner
    result = await db.execute(select(Accommodation).where(Accommodation.id == data.accommodation_id))
    accommodation = result.scalars().first()
    
    if not accommodation:
        raise HTTPException(status_code=404, detail="Accommodation not found")
    
    inquiry = Inquiry(
        accommodation_id=data.accommodation_id,
        student_id=current_user.id,
        owner_id=accommodation.owner_id,
        type=data.type,
        question=data.question,
        student_name=data.student_name,
        student_phone=data.student_phone,
        preferred_date=data.preferred_date,
        preferred_time=data.preferred_time,
        status=InquiryStatus.PENDING
    )
    
    db.add(inquiry)
    await db.commit()
    await db.refresh(inquiry)
    
    # Fetch owner details and send email in background
    
    # Fetch Owner
    owner_result = await db.execute(select(User).where(User.id == accommodation.owner_id))
    owner = owner_result.scalars().first()
    
    if owner and owner.email:
        background_tasks.add_task(
            send_inquiry_email_wrapper,
            recipient_email=owner.email,
            recipient_name=owner.name or "Venue Owner",
            inquiry_details={
                "venue_name": accommodation.name,
                "student_name": data.student_name or current_user.name,
                "student_email": current_user.email,
                "student_phone": data.student_phone,
                "question": data.question,
                "inquiry_date": inquiry.created_at.strftime("%d %B %Y at %I:%M %p") if inquiry.created_at else ""
            }
        )

    return InquiryResponse(
        id=inquiry.id,
        accommodation_id=inquiry.accommodation_id,
        student_id=inquiry.student_id,
        owner_id=inquiry.owner_id,
        type=inquiry.type.value,
        question=inquiry.question,
        student_name=inquiry.student_name,
        student_phone=inquiry.student_phone,
        preferred_date=inquiry.preferred_date,
        preferred_time=inquiry.preferred_time,
        reply=inquiry.reply,
        status=inquiry.status.value,
        created_at=inquiry.created_at,
        replied_at=inquiry.replied_at,
        accommodation_name=accommodation.name
    )

# Helper wrapper to avoid import inside function Issues
async def send_inquiry_email_wrapper(recipient_email, recipient_name, inquiry_details):
    from app.services.email_service import send_new_inquiry_notification_email
    try:
        await send_new_inquiry_notification_email(recipient_email, recipient_name, inquiry_details)
    except Exception as e:
        print(f"Background Email Error: {e}")
    



@router.get("/my", response_model=List[InquiryResponse])
async def get_my_inquiries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all inquiries sent by the current user (student view)."""
    result = await db.execute(
        select(Inquiry).where(Inquiry.student_id == current_user.id).order_by(Inquiry.created_at.desc())
    )
    inquiries = result.scalars().all()
    
    # Get accommodation names
    response = []
    for inq in inquiries:
        acc_result = await db.execute(select(Accommodation.name).where(Accommodation.id == inq.accommodation_id))
        acc_name = acc_result.scalar()
        
        response.append(InquiryResponse(
            id=inq.id,
            accommodation_id=inq.accommodation_id,
            student_id=inq.student_id,
            owner_id=inq.owner_id,
            type=inq.type.value,
            question=inq.question,
            student_name=inq.student_name,
            student_phone=inq.student_phone,
            preferred_date=inq.preferred_date,
            preferred_time=inq.preferred_time,
            reply=inq.reply,
            status=inq.status.value,
            created_at=inq.created_at,
            replied_at=inq.replied_at,
            accommodation_name=acc_name
        ))
    
    return response


@router.get("/received", response_model=List[InquiryResponse])
async def get_received_inquiries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all inquiries received by the current user (owner view)."""
    result = await db.execute(
        select(Inquiry).where(Inquiry.owner_id == current_user.id).order_by(Inquiry.created_at.desc())
    )
    inquiries = result.scalars().all()
    
    # Get accommodation names
    response = []
    for inq in inquiries:
        acc_result = await db.execute(select(Accommodation.name).where(Accommodation.id == inq.accommodation_id))
        acc_name = acc_result.scalar()
        
        response.append(InquiryResponse(
            id=inq.id,
            accommodation_id=inq.accommodation_id,
            student_id=inq.student_id,
            owner_id=inq.owner_id,
            type=inq.type.value,
            question=inq.question,
            student_name=inq.student_name,
            student_phone=inq.student_phone,
            preferred_date=inq.preferred_date,
            preferred_time=inq.preferred_time,
            reply=inq.reply,
            status=inq.status.value,
            created_at=inq.created_at,
            replied_at=inq.replied_at,
            accommodation_name=acc_name
        ))
    
    return response


@router.put("/{inquiry_id}/reply", response_model=InquiryResponse)
async def reply_to_inquiry(
    inquiry_id: str,
    data: InquiryReply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reply to an inquiry (owner only)."""
    result = await db.execute(select(Inquiry).where(Inquiry.id == inquiry_id))
    inquiry = result.scalars().first()
    
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    # Only owner can reply
    if inquiry.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the accommodation owner can reply")
    
    inquiry.reply = data.reply
    inquiry.status = InquiryStatus.REPLIED
    inquiry.replied_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(inquiry)
    
    # Get accommodation name and student info
    acc_result = await db.execute(select(Accommodation.name).where(Accommodation.id == inquiry.accommodation_id))
    acc_name = acc_result.scalar()
    
    # Get student email for notification
    try:
        from app.services.email_service import send_inquiry_response_email
        student_result = await db.execute(select(User).where(User.id == inquiry.student_id))
        student = student_result.scalars().first()
        
        if student and student.email:
            await send_inquiry_response_email(
                recipient_email=student.email,
                recipient_name=student.name or "Student",
                inquiry_details={
                    "venue_name": acc_name or "Accommodation",
                    "venue_owner": current_user.name or "Venue Owner",
                    "original_question": inquiry.question,
                    "response": data.reply,
                    "venue_phone": current_user.phone
                }
            )
    except Exception as email_error:
        print(f"Failed to send inquiry response email: {email_error}")
    
    return InquiryResponse(
        id=inquiry.id,
        accommodation_id=inquiry.accommodation_id,
        student_id=inquiry.student_id,
        owner_id=inquiry.owner_id,
        type=inquiry.type.value,
        question=inquiry.question,
        student_name=inquiry.student_name,
        student_phone=inquiry.student_phone,
        preferred_date=inquiry.preferred_date,
        preferred_time=inquiry.preferred_time,
        reply=inquiry.reply,
        status=inquiry.status.value,
        created_at=inquiry.created_at,
        replied_at=inquiry.replied_at,
        accommodation_name=acc_name
    )


@router.get("/count/pending")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get count of pending inquiries for the current owner."""
    result = await db.execute(
        select(Inquiry).where(
            Inquiry.owner_id == current_user.id,
            Inquiry.status == InquiryStatus.PENDING
        )
    )
    count = len(result.scalars().all())
    return {"count": count}
