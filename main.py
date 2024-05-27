from flask import Flask, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy import Integer, String, Float, select, desc
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from security import safe_requests
from dotenv import load_dotenv


import requests
import csv
import os

load_dotenv('.env')
TMDB_API_KEY: str = os.getenv('TMDB_API_KEY')


app = Flask(__name__)
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY
Bootstrap5(app)

TMDB_URL = "https://api.themoviedb.org/3/search/movie?query="

TMDB_HEADER = {
    "accept": "application/json","Authorization": "Bearer " + f"{TMDB_API_KEY}"
}

class Base(DeclarativeBase):
    pass

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///top-10-movies.db"
db = SQLAlchemy(model_class=Base)
db.init_app(app)


class Movie(db.Model):
    __tablename__ = "Top 10 Movies"
    id: Mapped[int] = (
        mapped_column(primary_key=True, nullable=False, name="ID"))
    title: Mapped[str] = mapped_column(unique=True, nullable=False, name="Title")
    year: Mapped[int] = mapped_column(nullable=False, name="Year")
    description: Mapped[str] = mapped_column(nullable=False, name="Description")
    rating : Mapped[float] = mapped_column(nullable=False, name="Rating")
    ranking : Mapped[int] = mapped_column(nullable=False, name="Ranking")
    review: Mapped[str] = mapped_column(nullable=False, name="Review")
    img_url: Mapped[str] = mapped_column(nullable=False, name="Image URL")

class EditForm(FlaskForm):
    new_rating = StringField(label="Your Rating Out of 10 e.g. 7.5")
    new_review = StringField(label="Your Review")
    submit = SubmitField('Submit')


class AddMovieForm(FlaskForm):
    title = StringField(label="Movie Title", validators=[DataRequired()])
    submit = SubmitField('Add Movie')

with app.app_context():
    db.create_all()



@app.route("/")
def home():
    with Session(app):
        select_all = db.session.execute(select(Movie).order_by(desc(Movie.ranking)))
        movies = select_all.scalars()
    return render_template("index.html", movies=movies)

@app.route("/edit/<int:id>", methods=['GET', 'POST'])
def edit(**kwargs):
    edit_form = EditForm()
    id = kwargs['id']
    with Session(app):
        desired_movie = db.get_or_404(Movie, id)
        if edit_form.validate_on_submit() and request.method == 'POST':
            if edit_form.new_rating.data != "":
                desired_movie.rating = edit_form.new_rating.data
                db.session.commit()
            if edit_form.new_review.data != "":
                desired_movie.review = edit_form.new_review.data
                db.session.commit()
            adjust_ranking()
            return redirect(url_for('home'))
    return render_template("edit.html", form =edit_form)

def adjust_ranking():
    movies_query = db.session.execute(select(Movie)).scalars()
    ratings_query = db.session.execute(select(Movie.rating)).scalars()
    ratings = list(ratings_query)
    ratings.sort(reverse=True)
    for rating in ratings:
        movie = db.session.execute(select(Movie).where(Movie.rating == rating)).scalar()
        movie.ranking = ratings.index(rating) + 1
        db.session.commit()




@app.route("/add/<int:id>")
def add_to_db(id):
    new_id = 0
    if request.method == 'GET':
        request.method = 'POST'
        movie_query = f"https://api.themoviedb.org/3/movie/{id}"
        tmdb_api_response = safe_requests.get(url=movie_query, headers=TMDB_HEADER).json()
        with Session(app):
            new_movie = Movie(title=tmdb_api_response['original_title'],
                              img_url=f"https://image.tmdb.org/t/p/w500{tmdb_api_response['poster_path']}",
                              year=tmdb_api_response['release_date'][0:4],
                              description=tmdb_api_response['overview'])
            db.session.add(new_movie)
            db.session.commit()
            new_id = db.session.query(Movie).count()
    return redirect(url_for("edit", id=new_id))



@app.route("/delete/<int:id>", methods=['GET'])
def delete(**kwargs):
    with Session(app):
        id = kwargs['id']
        undesired_movie = db.get_or_404(Movie, id)
        db.session.delete(undesired_movie)
        db.session.commit()
    return redirect(url_for('home'))


@app.route("/add", methods=['GET', 'POST'])
def add():
    add_form = AddMovieForm()
    if add_form.validate_on_submit() and request.method == 'POST':
        query = TMDB_URL + add_form.title.data
        tmdb_api = safe_requests.get(url=query, headers=TMDB_HEADER).json()
        results = tmdb_api['results']
        return render_template("select.html", movies=results)
    return render_template("add.html", form=add_form)

@app.route("/add")
def select_movies(movies):
    return  render_template("select.html", movies=movies)


if __name__ == '__main__':
    app.run(debug=True)
