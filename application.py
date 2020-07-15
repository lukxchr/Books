import os
import requests

from flask import Flask, jsonify, flash, render_template, request, redirect, url_for
from flask_session import Session
from sqlalchemy import or_
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse
from werkzeug.security import generate_password_hash

from model import Book, Review, User, db
from forms import LoginForm, RegistrationForm, ReviewForm
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
login = LoginManager(app)
login.login_view = 'login'
db.init_app(app)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@login.user_loader
def load_user(id_):
    return User.query.get(int(id_))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        form_username = form.username.data
        user = User.query.filter_by(username=f"{form_username}").first()
        if user is None or not user.check_password(form.password.data):
            flash("Incorrect username or password")
            return render_template("login.html", form=form)
        else:
            flash(f'You are now logged in as {user.username}')
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('index')
            return redirect(next_page)
    return render_template("login.html", form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data,
                    password_hash=generate_password_hash(form.password.data))
        db.session.add(user)
        db.session.commit()
        flash('You are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "GET":
        return render_template("index.html")
    elif request.method == "POST":
        search_query = request.form.get("search-query")
        return redirect(url_for("search", query=search_query))


@app.route("/search/<path:query>")
@login_required
def search(query):
    books = Book.query.filter(
        or_(Book.title.ilike(f"%{query}%"),
            Book.author.ilike(f"%{query}%"),
            Book.isbn.ilike(f"%{query}%"))).all()
    if not books:
        flash(f"No books for your query ({query}). Please try again.")
        return redirect(url_for("index"))
    return render_template("index.html", search_results=books, search_query=query)


@app.route("/book/<int:book_id>", methods=["GET", "POST"])
@login_required
def book(book_id):
    book = Book.query.get(book_id)
    form = ReviewForm()
    reviews = Review.query.filter(Review.book_id == book.id).all()
    review_by_current_user = None
    for review in reviews:
        if review.user_id == current_user.id:
            review_by_current_user = review
            break

    #POST request(review form is submitted)
    if form.validate_on_submit():
        if review_by_current_user:
            flash("You already reviewed this book")
        else:
            review = Review(title=form.title.data,
                            content=form.content.data,
                            rating=int(form.rating.data),
                            user_id=int(current_user.id),
                            book_id=int(book_id))
            db.session.add(review)
            db.session.commit()
            flash("Review added")
            return redirect(url_for("book", book_id=book_id))
    elif request.method == "POST":
        flash("Please fill out all review fields.")

    #get extra book details from goodreads and google
    goodreads_rating, goodreads_ratings_count = get_goodreads_details(
        book.isbn, Config.GOODREADS_API_KEY)
    google_book_info = get_google_details(book.isbn)
    google_description, google_cover = google_book_info["description"], google_book_info["cover"]
    book_details = dict(goodreads_rating=goodreads_rating,
                        goodreads_ratings_count=goodreads_ratings_count,
                        description=google_description, cover=google_cover)
    return render_template("book.html", book=book, form=form, reviews=reviews,
                           review_by_current_user=review_by_current_user,
                           book_details=book_details)


@app.route("/editReview/<int:review_id>", methods=["GET", "POST"])
@login_required
def edit_review(review_id):
    review = Review.query.get(review_id)
    if not review or review.user_id != current_user.id:
        return "Access denied"
    form = ReviewForm()
    if form.validate_on_submit():
        review.rating = int(form.rating.data)
        review.title = form.title.data
        review.content = form.content.data
        db.session.add(review)
        db.session.commit()
        flash("Review updated")
        return redirect(url_for('book', book_id=review.book_id))
    elif request.method == 'GET':
        form.rating.data = f"{review.rating}"
        form.title.data = review.title
        form.content.data = review.content
    else:
        flash("Please fill out all review fields.")
    return render_template("edit_review.html", form=form, review=review)


@app.route("/deleteReview/<int:review_id>", methods=["GET"])
@login_required
def delete_review(review_id):
    review = Review.query.filter(Review.id == review_id).first()
    if not review or review.user_id != current_user.id:
        return "Access denied"
    else:
        db.session.delete(review)
        db.session.commit()
        flash("Review deleted")
        return redirect(url_for('book', book_id=review.book_id))


@app.route("/api/<isbn>")
def book_json(isbn):
    print("api for isbn: " + str(isbn))
    try:
        book = Book.query.filter(Book.isbn == isbn).first()
        goodreads_rating, goodreads_ratings_count = get_goodreads_details(
            book.isbn, "ow2ypDLGjjsQgTc2etsz7w")
        return jsonify({
            "title": book.title,
            "author": book.author,
            "year": book.year,
            "isbn": book.isbn,
            "review_count": goodreads_ratings_count,
            "average_score": goodreads_rating
            })
    except:
        return jsonify({"success" : False})

#utils


def get_goodreads_details(isbn, api_key):
    try:
        res = requests.get("https://www.goodreads.com/book/review_counts.json",
                           params={"key": api_key, "isbns": isbn})
        goodreads_rating = res.json()['books'][0]['average_rating']
        goodreads_ratings_count = res.json()['books'][0]['ratings_count']
    except:
        goodreads_rating = None
        goodreads_ratings_count = None
    return (goodreads_rating, goodreads_ratings_count)


def get_google_details(isbn):
    re = requests.get(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}")
    try:
        description = re.json()["items"][0]["volumeInfo"]["description"]
    except:
        description = None
    try:
        cover_image_url = re.json()["items"][0]["volumeInfo"]["imageLinks"]["thumbnail"]
    except:
        cover_image_url = None
    return {"description" : description, "cover": cover_image_url}


if __name__ == '__main__':
    app.run(debug=True)
