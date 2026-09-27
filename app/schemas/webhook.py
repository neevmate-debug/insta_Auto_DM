"""
Pydantic schema definitions for Meta Webhook events.
Based on the official Instagram Graph API webhook payload structure:
https://developers.facebook.com/docs/graph-api/webhooks/getting-started
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class WebhookSender(BaseModel):
    """Details about the user who left the comment."""
    id: str = Field(..., description="Instagram Scoped ID (IGSID) or Facebook user ID")
    username: Optional[str] = Field(None, description="Instagram handle / username if provided")


class WebhookMedia(BaseModel):
    """Details about the media (post/reel) commented on."""
    id: str = Field(..., description="Media ID on Instagram")
    media_product_type: Optional[str] = Field(None, description="e.g., FEED, REELS")


class WebhookCommentValue(BaseModel):
    """
    Value structure for an Instagram comment change event.
    """
    id: str = Field(..., description="Unique comment ID")
    text: Optional[str] = Field(None, description="Text content of the comment")
    from_: Optional[WebhookSender] = Field(None, alias="from", description="Comment author details")
    media: Optional[WebhookMedia] = Field(None, description="Post/reel associated with the comment")
    parent_id: Optional[str] = Field(None, description="Parent comment ID if this is a reply")


class WebhookChange(BaseModel):
    """Individual change item inside an entry."""
    field: str = Field(..., description="Name of the changed field, e.g. 'comments' or 'mentions'")
    value: Dict[str, Any] = Field(..., description="Payload data for the change")


class WebhookEntry(BaseModel):
    """Entry element within the top-level webhook envelope."""
    id: str = Field(..., description="Target Page or Instagram Business Account ID")
    time: int = Field(..., description="Epoch timestamp of the event")
    changes: Optional[List[WebhookChange]] = Field(default_factory=list)


class MetaWebhookPayload(BaseModel):
    """
    Root envelope for Meta Webhook POST notifications.
    The object type for Instagram is typically 'instagram'.
    """
    object: str = Field(..., description="Target object type, e.g., 'instagram' or 'page'")
    entry: List[WebhookEntry] = Field(default_factory=list, description="List of entry events")
