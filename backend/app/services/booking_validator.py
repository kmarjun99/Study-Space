"""
Booking Duration Validator Service
Handles validation, price calculation, and date calculations for flexible booking durations
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import HTTPException
import json
import calendar


class BookingDurationType:
    """Booking duration type constants"""
    ONE_DAY = "1_DAY"
    ONE_WEEK = "1_WEEK"
    ONE_MONTH = "1_MONTH"
    THREE_MONTHS = "3_MONTHS"
    SIX_MONTHS = "6_MONTHS"
    
    ALL = [ONE_DAY, ONE_WEEK, ONE_MONTH, THREE_MONTHS, SIX_MONTHS]
    
    LABELS = {
        ONE_DAY: "1 Day",
        ONE_WEEK: "1 Week",
        ONE_MONTH: "1 Month",
        THREE_MONTHS: "3 Months",
        SIX_MONTHS: "6 Months"
    }


class BookingValidator:
    """Service for booking duration validation and calculations"""
    
    @staticmethod
    def parse_duration_prices(duration_prices_str: Optional[str]) -> Dict[str, Optional[float]]:
        """Parse duration_prices JSON string to dict"""
        if not duration_prices_str:
            return {}
        
        try:
            prices = json.loads(duration_prices_str)
            return prices
        except (json.JSONDecodeError, TypeError):
            return {}
    
    @staticmethod
    def parse_allowed_durations(allowed_durations_str: Optional[str]) -> List[str]:
        """Parse allowed_booking_durations JSON string to list"""
        if not allowed_durations_str:
            return [BookingDurationType.ONE_MONTH]
        
        try:
            durations = json.loads(allowed_durations_str)
            return durations if isinstance(durations, list) else [BookingDurationType.ONE_MONTH]
        except (json.JSONDecodeError, TypeError):
            return [BookingDurationType.ONE_MONTH]
    
    @staticmethod
    async def validate_duration_allowed(reading_room, duration_type: str):
        """Check if duration type is allowed for this reading room"""
        allowed_durations = BookingValidator.parse_allowed_durations(
            reading_room.allowed_booking_durations
        )
        
        if duration_type not in allowed_durations:
            raise HTTPException(
                status_code=400,
                detail=f"Duration type '{duration_type}' is not allowed for this venue. Allowed durations: {allowed_durations}"
            )
    
    @staticmethod
    def get_duration_price(reading_room, duration_type: str, fallback_price: float) -> float:
        """
        Get price for specific duration type.
        Uses custom price if set by owner, otherwise calculates proportional price.
        """
        duration_prices = BookingValidator.parse_duration_prices(
            reading_room.duration_prices
        )
        
        # Return custom price if owner has set it
        custom_price = duration_prices.get(duration_type)
        if custom_price is not None and custom_price > 0:
            return float(custom_price)
        
        # Calculate proportional fallback price based on monthly rate
        base_monthly_price = reading_room.price_start or fallback_price
        
        if duration_type == BookingDurationType.ONE_DAY:
            return float(base_monthly_price / 30)  # ~1/30 of monthly
        elif duration_type == BookingDurationType.ONE_WEEK:
            return float(base_monthly_price / 4)   # ~1/4 of monthly
        elif duration_type == BookingDurationType.ONE_MONTH:
            return float(base_monthly_price)
        elif duration_type == BookingDurationType.THREE_MONTHS:
            return float(base_monthly_price * 3)
        elif duration_type == BookingDurationType.SIX_MONTHS:
            return float(base_monthly_price * 6)
        
        # Use cabin price as last resort fallback
        return fallback_price
    
    @staticmethod
    def validate_custom_prices_set(reading_room, duration_type: str):
        """Validate that price can be calculated (either custom or proportional fallback)"""
        duration_prices = BookingValidator.parse_duration_prices(
            reading_room.duration_prices
        )
        
        price = duration_prices.get(duration_type)
        
        # If custom price is set and valid, OK
        if price is not None and price > 0:
            return
        
        # Check if we can use proportional fallback (base price exists)
        if reading_room.price_start and reading_room.price_start > 0:
            return  # Can calculate proportional price
        
        # No custom price and no base price to calculate from
        raise HTTPException(
            status_code=400,
            detail=f"Cannot calculate price for '{duration_type}'. Reading room has no base price configured."
        )
    
    @staticmethod
    def calculate_end_date(start_date: datetime, duration_type: str) -> datetime:
        """Calculate end date based on duration type and start date"""
        
        if duration_type == BookingDurationType.ONE_DAY:
            return start_date + timedelta(days=1)
        
        elif duration_type == BookingDurationType.ONE_WEEK:
            return start_date + timedelta(weeks=1)
        
        elif duration_type == BookingDurationType.ONE_MONTH:
            # Add 1 month (handle month boundaries correctly)
            return BookingValidator._add_months(start_date, 1)
        
        elif duration_type == BookingDurationType.THREE_MONTHS:
            return BookingValidator._add_months(start_date, 3)
        
        elif duration_type == BookingDurationType.SIX_MONTHS:
            return BookingValidator._add_months(start_date, 6)
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid duration type: {duration_type}"
            )
    
    @staticmethod
    def _add_months(start_date: datetime, months: int) -> datetime:
        """
        Add months to a date, handling month boundaries correctly.
        Example: Jan 31 + 1 month = Feb 28/29 (last day of Feb)
        """
        # Calculate target month and year
        month = start_date.month + months
        year = start_date.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        
        # Handle day overflow (e.g., Jan 31 -> Feb has no 31st)
        last_day_of_month = calendar.monthrange(year, month)[1]
        day = min(start_date.day, last_day_of_month)
        
        return datetime(
            year=year,
            month=month,
            day=day,
            hour=start_date.hour,
            minute=start_date.minute,
            second=start_date.second,
            microsecond=start_date.microsecond
        )
    
    @staticmethod
    def format_duration_label(duration_type: str) -> str:
        """Get human-readable label for duration type"""
        return BookingDurationType.LABELS.get(duration_type, duration_type)
    
    @staticmethod
    def validate_duration_prices_schema(duration_prices: Dict[str, float]) -> Dict[str, float]:
        """Validate and clean duration prices dict"""
        validated = {}
        
        for duration_type in BookingDurationType.ALL:
            price = duration_prices.get(duration_type)
            if price is not None:
                if not isinstance(price, (int, float)) or price < 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid price for {duration_type}: must be a positive number"
                    )
                validated[duration_type] = float(price)
            else:
                validated[duration_type] = None
        
        return validated


booking_validator = BookingValidator()
