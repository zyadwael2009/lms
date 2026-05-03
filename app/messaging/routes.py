from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.messaging.forms import MessageForm
from app.models import Message, User
from app.utils.decorators import approved_required


messaging_bp = Blueprint("messaging", __name__, template_folder="../templates")


@messaging_bp.route("/inbox")
@login_required
@approved_required
def inbox():
    """Shows messages received by the current user."""

    messages = (
        Message.query.filter_by(receiver_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return render_template("messaging/inbox.html", messages=messages)


@messaging_bp.route("/sent")
@login_required
@approved_required
def sent_messages():
    """Shows messages sent by the current user."""

    messages = (
        Message.query.filter_by(sender_id=current_user.id)
        .order_by(Message.created_at.desc())
        .all()
    )
    return render_template("messaging/sent.html", messages=messages)


@messaging_bp.route("/compose", methods=["GET", "POST"])
@login_required
@approved_required
def compose():
    """Composes and sends a new direct message."""

    form = MessageForm()

    recipient_candidates = (
        User.query.filter(User.id != current_user.id, User.is_active.is_(True), User.is_approved.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )
    form.receiver_id.choices = [(user.id, f"{user.full_name} ({user.email})") for user in recipient_candidates]

    if not form.receiver_id.choices:
        flash("No available recipients yet.", "warning")
        return redirect(url_for("messaging.inbox"))

    if form.validate_on_submit():
        receiver = User.query.get(form.receiver_id.data)
        if not receiver or receiver.id == current_user.id:
            flash("Invalid recipient.", "danger")
            return render_template("messaging/compose.html", form=form)

        message = Message(
            sender_id=current_user.id,
            receiver_id=receiver.id,
            subject=(form.subject.data or "").strip() or None,
            body=form.body.data.strip(),
            is_read=False,
        )
        db.session.add(message)
        db.session.commit()

        flash("Message sent successfully.", "success")
        return redirect(url_for("messaging.sent_messages"))

    return render_template("messaging/compose.html", form=form)


@messaging_bp.route("/<int:message_id>")
@login_required
@approved_required
def view_message(message_id: int):
    """Displays one message detail page and marks it as read for receiver."""

    message = Message.query.get_or_404(message_id)

    if message.sender_id != current_user.id and message.receiver_id != current_user.id:
        flash("You are not allowed to open this message.", "danger")
        return redirect(url_for("messaging.inbox"))

    if message.receiver_id == current_user.id and not message.is_read:
        message.is_read = True
        db.session.commit()

    return render_template("messaging/view_message.html", message=message)
