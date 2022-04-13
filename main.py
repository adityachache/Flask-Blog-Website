import os
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from functools import wraps

from flask_gravatar import Gravatar
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from forms import CreatePostForm, CreateRegisterForm, LoginForm, CommentForm
from flask_ckeditor import CKEditor
import datetime as dt
import smtplib

# Initializing the app
app = Flask(__name__)
# Initialize the secret key
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
# Ckeditor
app.config['CKEDITOR_PKG_TYPE'] = 'standard'
ckeditor = CKEditor(app)

# Include Bootstrap for flask
Bootstrap(app)

# Setting up the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize instance of login manager class. helps to implement methods such as is_loggedin, is_authenticated, etc
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


today = dt.datetime.now().year
full_date = dt.datetime.now()
EMAIL = "fenixfirea380@gmail.com"
PASSWORD = os.environ.get("PASSWORD")

# Initialize instance of Gravatar class (used to give profile pic to comments)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# Creating Table
class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(250), nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object, the "posts" refers to the posts protperty in the User class.
    author = relationship("User", back_populates="posts")

    # ***************Parent Relationship*************#
    comments = relationship("Comment", back_populates="parent_post")


# Creating User Table
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")

    # ***************Parent Relationship*************#
    comments = relationship("Comment", back_populates="user_comment")


# Creating comment table
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # ***************Child Relationship*************#
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user_comment = relationship("User", back_populates="comments")


# if database is not created then only this line will run
if not os.path.isfile("sqlite:///blog.db"):
    db.create_all()


# send a mail to the owner of the website through the contact me section
def send_mail(message):
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(user=EMAIL, password=PASSWORD)
        connection.sendmail(from_addr=EMAIL,
                            to_addrs="aditya.chache@rediffmail.com",
                            msg=f"Subject:Blog Message\n\n{message}")


# admin only route
def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403, description="You are not authorised to access this route")
        return function(*args, **kwargs)
    return decorated_function


# def get_blog_posts():
#     url = "https://api.npoint.io/52b4b0536bbb7d7e7059"
#     response = requests.get(url=url)
#     data = response.json()
#     return data

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def home():
    blog_posts = BlogPost.query.all()
    return render_template("index.html", posts=blog_posts,
                           curr_year=today,
                           logged_in=current_user.is_authenticated,
                           current_user=current_user)


@app.route("/about")
def about():
    return render_template("about.html", curr_year=today, logged_in=current_user.is_authenticated)


@app.route("/post/<int:post_number>", methods=["GET", "POST"])
def post(post_number):
    requested_post = BlogPost.query.get(post_number)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_form.comment.data,
            user_comment=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html",
                           posts=requested_post,
                           curr_year=today,
                           logged_in=current_user.is_authenticated,
                           current_user=current_user,
                           form=comment_form)


@app.route("/new-post", methods=["POST", "GET"])
@admin_only
def new_post():
    form = CreatePostForm()
    # title = form.title.data
    if form.validate_on_submit():
        newpost = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            img_url=form.img_url.data,
            body=form.body.data,
            author=current_user,
            date=full_date.strftime("%B %d, %Y")
        )
        db.session.add(newpost)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("make-post.html",
                           form=form,
                           logged_in=current_user.is_authenticated,
                           current_user=current_user)


@app.route("/edit-post/<int:post_number>", methods=["GET", "POST"])
@admin_only
def edit_post(post_number):
    blog_post = BlogPost.query.get(post_number)
    edit_form = CreatePostForm(
        title=blog_post.title,
        subtitle=blog_post.subtitle,
        img_url=blog_post.img_url,
        author=current_user,
        body=blog_post.body
    )
    if edit_form.validate_on_submit():
        blog_post.title = edit_form.title.data
        blog_post.subtitle = edit_form.subtitle.data
        blog_post.img_url = edit_form.img_url.data
        # blog_post.author = edit_form.author.data
        blog_post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for('post', post_number=post_number))
    return render_template("make-post.html", form=edit_form,
                           is_edit=True,
                           post_number=post_number,
                           logged_in=current_user.is_authenticated,
                           current_user=current_user)


@app.route("/delete/<int:post_number>")
@admin_only
def delete(post_number):
    post_to_delete = BlogPost.query.get(post_number)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('home'))


@app.route("/contact", methods=['POST', 'GET'])
def contact():
    if request.method == "POST":
        data = request.form
        name = data['name']
        email = data['email']
        phone = data['phone']
        message = data['message']
        formatted_message = f"Name: {name}\nPhone: {phone}\nEmail: {email}\nMessage: {message}"
        send_mail(formatted_message)
        return render_template("contact.html", curr_year=today, msg_sent=True)
    return render_template("contact.html", curr_year=today, msg_sent=False, logged_in=current_user.is_authenticated)


@app.route("/register", methods=["GET", "POST"])
def register():
    register_form = CreateRegisterForm()
    if register_form.validate_on_submit():
        if User.query.filter_by(email=register_form.email.data).first():
            flash("Email already exists. Try to login instead")
            return redirect(url_for("login"))

        new_user = User(
            email=register_form.email.data,
            password=generate_password_hash(password=register_form.password.data,
                                            method='pbkdf2:sha256',
                                            salt_length=8),
            name=register_form.name.data
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("home"))
    return render_template("register.html", form=register_form, logged_in=current_user.is_authenticated)


@app.route("/login", methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if user and check_password_hash(user.password, login_form.password.data):
            login_user(user)
            return redirect(url_for('home'))
        elif not user:
            flash("Email doesn't exists. Try registering Instead")
            return redirect(url_for('register'))
        else:
            flash("Password is wrong. Enter Correct password")
            return redirect(url_for("login"))

    return render_template('login.html', logged_in=current_user.is_authenticated, form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)
