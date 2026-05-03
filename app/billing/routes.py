from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    PaymentStatus,
    PaymentTransaction,
    SubscriptionPlan,
    SubscriptionStatus,
    UserSubscription,
)
from app.utils.decorators import approved_required


billing_bp = Blueprint("billing", __name__, template_folder="../templates")


def _calculate_end_date(plan: SubscriptionPlan) -> datetime | None:
    """Infers a subscription end date from billing cycle."""

    cycle = (plan.billing_cycle or "").strip().lower()
    now = datetime.now(timezone.utc)

    if cycle == "monthly":
        return now + timedelta(days=30)
    if cycle == "yearly":
        return now + timedelta(days=365)

    # Custom cycles can be handled later by explicit duration fields.
    return None


@billing_bp.route("/plans")
@login_required
@approved_required
def plans():
    """Displays active subscription plans and current user subscriptions."""

    plans_list = SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.price.asc()).all()

    subscriptions = (
        UserSubscription.query.filter_by(user_id=current_user.id)
        .order_by(UserSubscription.created_at.desc())
        .all()
    )

    active_subscription = next(
        (subscription for subscription in subscriptions if subscription.status == SubscriptionStatus.ACTIVE),
        None,
    )

    return render_template(
        "billing/plans.html",
        plans=plans_list,
        subscriptions=subscriptions,
        active_subscription=active_subscription,
    )


@billing_bp.route("/subscribe/<int:plan_id>", methods=["POST"])
@login_required
@approved_required
def subscribe(plan_id: int):
    """Creates a simulated successful payment and activates a plan."""

    plan = SubscriptionPlan.query.get_or_404(plan_id)
    if not plan.is_active:
        flash("This plan is not currently available.", "warning")
        return redirect(url_for("billing.plans"))

    existing_active = UserSubscription.query.filter_by(
        user_id=current_user.id,
        status=SubscriptionStatus.ACTIVE,
    ).first()

    if existing_active:
        existing_active.status = SubscriptionStatus.CANCELED
        existing_active.auto_renew = False
        existing_active.ends_at = datetime.now(timezone.utc)

    new_subscription = UserSubscription(
        user_id=current_user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        starts_at=datetime.now(timezone.utc),
        ends_at=_calculate_end_date(plan),
        auto_renew=True,
        payment_provider="manual-demo",
        payment_reference=f"SUB-{current_user.id}-{plan.id}-{int(datetime.now(timezone.utc).timestamp())}",
    )
    db.session.add(new_subscription)
    db.session.flush()

    transaction = PaymentTransaction(
        user_subscription_id=new_subscription.id,
        amount=plan.price,
        currency=plan.currency,
        status=PaymentStatus.COMPLETED,
        provider="manual-demo",
        provider_transaction_id=f"TX-{new_subscription.id}-{int(datetime.now(timezone.utc).timestamp())}",
        paid_at=datetime.now(timezone.utc),
    )
    db.session.add(transaction)
    db.session.commit()

    flash(f"Subscription to {plan.name} activated successfully.", "success")
    return redirect(url_for("billing.plans"))


@billing_bp.route("/subscriptions")
@login_required
@approved_required
def subscriptions():
    """Lists subscription history for current user."""

    records = (
        UserSubscription.query.filter_by(user_id=current_user.id)
        .order_by(UserSubscription.created_at.desc())
        .all()
    )
    return render_template("billing/subscriptions.html", subscriptions=records)


@billing_bp.route("/subscriptions/<int:subscription_id>/cancel", methods=["POST"])
@login_required
@approved_required
def cancel_subscription(subscription_id: int):
    """Allows users to cancel auto-renew on an active subscription."""

    subscription = UserSubscription.query.get_or_404(subscription_id)

    if subscription.user_id != current_user.id:
        flash("You cannot cancel this subscription.", "danger")
        return redirect(url_for("billing.subscriptions"))

    if subscription.status != SubscriptionStatus.ACTIVE:
        flash("This subscription is not active.", "warning")
        return redirect(url_for("billing.subscriptions"))

    subscription.status = SubscriptionStatus.CANCELED
    subscription.auto_renew = False
    subscription.ends_at = datetime.now(timezone.utc)

    db.session.commit()
    flash("Subscription canceled.", "info")
    return redirect(url_for("billing.subscriptions"))
