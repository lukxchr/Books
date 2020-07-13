from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
from wtforms.widgets import TextArea
from model import User, Book

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

class ReviewForm(FlaskForm):
	title = StringField('Title', 
        validators=[DataRequired()], 
        render_kw={"placeholder": "Review title", "style": "width:50vw"})
	content = StringField('Review', validators=[DataRequired()], 
        widget=TextArea(), 
        render_kw={"placeholder": "Your review...", "style": "width:50vw;height:30vh"})
	rating = RadioField('Your Rating:', 
        choices=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], 
        validators=[DataRequired()])
	submit = SubmitField('Add Review')