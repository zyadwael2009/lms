from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class MessageForm(FlaskForm):
    """Form for sending direct user-to-user messages."""

    receiver_id = SelectField("Send to", coerce=int, validators=[DataRequired()])
    subject = StringField("Subject", validators=[Optional(), Length(max=200)])
    body = TextAreaField("Message", validators=[DataRequired(), Length(min=1, max=5000)])
    submit = SubmitField("Send message")
