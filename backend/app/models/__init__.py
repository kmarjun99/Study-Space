# Trust & Safety Models
from app.models.user import User, UserRole, VerificationStatus, KYCStatus, GSTRegistrationType
from app.models.reading_room import ReadingRoom, Cabin, CabinStatus, ListingStatus, MaintenanceStatus, PriceDisplayMode
from app.models.accommodation import Accommodation
from app.models.booking import Booking, BookingStatus, PaymentStatus, SettlementStatus, GSTTreatment
from app.models.review import Review
from app.models.waitlist import WaitlistEntry
from app.models.favorite import Favorite
from app.models.city import CitySettings
from app.models.ad import Ad
from app.models.ad_category import AdCategory, CategoryStatus
from app.models.location import Location
from app.models.inquiry import Inquiry, InquiryType, InquiryStatus

# Trust & Safety Governance
from app.models.trust_flag import TrustFlag, TrustFlagType, TrustFlagStatus
from app.models.reminder import Reminder, ReminderType, ReminderStatus
from app.models.audit_log import AuditLog, AuditActionType

# Payments & Refunds
from app.models.refund import Refund, RefundStatus, RefundReason
from app.models.payment_transaction import PaymentTransaction, PaymentMethod, PaymentGateway

# Boost / Promotions
from app.models.boost_plan import BoostPlan, BoostPlanStatus, BoostApplicableTo, BoostPlacement
from app.models.boost_request import BoostRequest, BoostRequestStatus, VenueType

# Subscription Plans
from app.models.subscription_plan import SubscriptionPlan

# OTP & Password Reset
from app.models.otp import OTP, PasswordReset

# ---- Accounting / Tax / Settlement (Transaction-Flow Foundation) ----
from app.models.chart_of_accounts import ChartOfAccounts
from app.models.ledger_entry import LedgerEntry
from app.models.tax_config import TaxConfig
from app.models.tax_snapshot import TaxSnapshot
from app.models.party import Party
from app.models.webhook_event import WebhookEvent
from app.models.invoice_series_counter import InvoiceSeriesCounter
from app.models.owner_charge import (
    OwnerCharge,
    OwnerChargeType,
    OwnerChargeStatus,
    ListingType,
)
from app.models.invoice import Invoice, InvoiceDocType
from app.models.settlement import (
    SettlementRun,
    SettlementLine,
    SettlementStatus as SettlementRunStatus,
    SettlementLineKind,
)

# ---- Intelligence layer (Phase 1: event firehose + consent) ----
from app.models.user_event import UserEvent, EventCategory, EventEntityType
from app.models.user_consent_preferences import UserConsentPreferences

# ---- Intelligence layer (Phase 2: derived profile + intent) ----
from app.models.user_intelligence_profile import UserIntelligenceProfile, IntentLevel

# ---- Intelligence layer (Phase 3: rule-based recommendations) ----
from app.models.recommendation_log import RecommendationLog, RecommendationSurface

# ---- Intelligence layer (Phase 4A: rule-based segments) ----
from app.models.user_segment import (
    UserSegment, UserSegmentMembership, SegmentRuleType,
)

# ---- Intelligence layer (Phase 4B: campaigns + attribution) ----
from app.models.campaign import (
    Campaign, CampaignDelivery,
    CampaignStatus, CampaignChannel, DeliveryStatus,
)

# ---- Intelligence layer (Phase 4C: notification automation) ----
from app.models.notification_rule import NotificationRule, TriggerType

# ---- Intelligence layer (Phase 6: experiments + cohorts + ML) ----
from app.models.experiment import (
    Experiment, ExperimentAssignment, ExperimentStatus,
)

# ---- SEO geographic hierarchy (national scale) ----
from app.models.seo_location import SeoLocation, LocationKind

# ---- Support tickets ----
from app.models.support_ticket import (
    SupportTicket,
    SupportCategory,
    SupportTicketPriority,
    SupportTicketStatus,
)
