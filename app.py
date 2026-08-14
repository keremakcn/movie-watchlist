import json
import os

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, render_template, request, redirect
from cs50 import SQL

app = Flask(__name__)

db = SQL("sqlite:///movies.db")
def get_tmdb_details(tmdb_id):
    token = os.environ.get("TMDB_ACCESS_TOKEN")

    if not tmdb_id or not token:
        return None

    api_request = Request(
        f"https://api.themoviedb.org/3/movie/{tmdb_id}?language=en-US&append_to_response=credits",
        headers={"Authorization": f"Bearer {token}"}
    )

    try:
        with urlopen(api_request, timeout=5) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError):
        return None

    poster_path = data.get("poster_path")
    credits = data.get("credits", {})

    director = next(
        (
            person["name"]
            for person in credits.get("crew", [])
            if person.get("job") == "Director"
        ),
        None
    )

    cast = [
        person["name"]
        for person in credits.get("cast", [])[:5]
    ]

    return {
        "overview": data.get("overview"),
        "runtime": data.get("runtime"),
        "director": director,
        "cast": cast,
        "poster_url": (
            f"https://image.tmdb.org/t/p/w500{poster_path}"
            if poster_path
            else None
        )
    }
def get_tmdb_poster(tmdb_id):
    token = os.environ.get("TMDB_ACCESS_TOKEN")

    if not tmdb_id or not token:
        return None

    api_request = Request(
        f"https://api.themoviedb.org/3/movie/{tmdb_id}?language=en-US",
        headers={"Authorization": f"Bearer {token}"}
    )

    try:
        with urlopen(api_request, timeout=5) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError):
        return None

    poster_path = data.get("poster_path")

    if not poster_path:
        return None

    return f"https://image.tmdb.org/t/p/w342{poster_path}"


@app.route("/")
def index():
    status = request.args.get("status")
    favorite = request.args.get("favorite")
    sort = request.args.get("sort")

    query = """
        SELECT movies.*, movie_catalog.tmdb_id
        FROM movies
        LEFT JOIN movie_catalog
        ON movies.catalog_id = movie_catalog.id
    """
    params = []

    if status:
        query += " WHERE status = ?"
        params.append(status)
    elif favorite:
        query += " WHERE favorite = 1"

    if sort == "high":
        query += " ORDER BY rating DESC"
    elif sort == "low":
        query += " ORDER BY rating ASC"
    elif sort == "newest":
        query += " ORDER BY year DESC"
    elif sort == "oldest":
        query += " ORDER BY year ASC"
    else:
        query += """
            ORDER BY
                CASE
                    WHEN favorite = 1 THEN 1
                    WHEN status = 'Watched' THEN 2
                    WHEN status = 'Watchlist' THEN 3
                    ELSE 4
                END,
                id DESC
        """

    movies = db.execute(query, *params)
    for movie in movies:
        movie["poster_url"] = get_tmdb_poster(movie["tmdb_id"])
    recent_movies = db.execute(
        "SELECT * FROM movies ORDER BY id DESC LIMIT 5"
    )

    watchlist_movies = db.execute(
        "SELECT COUNT(*) AS total FROM movies WHERE status = ?",
        "Watchlist"
    )[0]["total"]

    watched_movies = db.execute(
        "SELECT COUNT(*) AS total FROM movies WHERE status = ?",
        "Watched"
    )[0]["total"]

    favorite_movies = db.execute(
        "SELECT COUNT(*) AS total FROM movies WHERE favorite = 1"
    )[0]["total"]

    average_rating = db.execute(
        "SELECT ROUND(AVG(rating), 1) AS average_rating FROM movies WHERE rating IS NOT NULL"
    )[0]["average_rating"]

    return render_template(
        "index.html",
        movies=movies,
        recent_movies=recent_movies,
        watchlist_movies=watchlist_movies,
        watched_movies=watched_movies,
        favorite_movies=favorite_movies,
        average_rating=average_rating
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        title = request.form.get("title")
        year = request.form.get("year")
        genre = request.form.get("genre")
        status = request.form.get("status")
        rating = request.form.get("rating")
        note = request.form.get("note")

        db.execute(
            """
            INSERT INTO movies
            (title, year, genre, status, rating, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            title,
            year,
            genre,
            status,
            rating,
            note,
        )

        return redirect("/")

    return render_template("add.html")


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    if query:
        words = query.split()

        conditions = []
        params = []

        for word in words:
            conditions.append("title LIKE ?")
            params.append("%" + word + "%")

        sql = """
            SELECT *
            FROM movie_catalog
            WHERE
        """

        sql += " AND ".join(conditions)

        sql += """
            ORDER BY title
            LIMIT 20
        """

        results = db.execute(sql, *params)

    else:
        results = []

    return render_template("search.html", results=results, query=query)

@app.route("/add_from_catalog", methods=["POST"])
def add_from_catalog():
    movie_id = request.form.get("movie_id")

    movies = db.execute(
        "SELECT * FROM movie_catalog WHERE id = ?",
        movie_id
    )

    if not movies:
        return redirect("/search")

    movie = movies[0]

    existing = db.execute(
        "SELECT id FROM movies WHERE catalog_id = ?",
        movie_id
    )

    if existing:
        return redirect(f"/movie/{existing[0]['id']}")

    db.execute(
        """
        INSERT INTO movies
        (title, year, genre, status, catalog_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        movie["title"],
        movie["year"],
        movie["genre"],
        "Watchlist",
        movie["id"],
    )

    new_movie = db.execute(
        "SELECT id FROM movies WHERE catalog_id = ? ORDER BY id DESC LIMIT 1",
        movie_id
    )[0]

    return redirect("/")

@app.route("/add_watched_from_catalog", methods=["POST"])
def add_watched_from_catalog():
    movie_id = request.form.get("movie_id")

    movies = db.execute(
        "SELECT * FROM movie_catalog WHERE id = ?",
        movie_id
    )

    if not movies:
        return redirect("/search")

    movie = movies[0]

    existing = db.execute(
        "SELECT id FROM movies WHERE catalog_id = ?",
        movie_id
    )

    if existing:
        return redirect(f"/movie/{existing[0]['id']}")

    db.execute(
        """
        INSERT INTO movies
        (title, year, genre, status, watched_date, catalog_id)
        VALUES (?, ?, ?, ?, DATE('now'), ?)
        """,
        movie["title"],
        movie["year"],
        movie["genre"],
        "Watched",
        movie["id"],
    )

    return redirect("/")


@app.route("/edit/<int:movie_id>", methods=["GET", "POST"])
def edit(movie_id):
    movies = db.execute(
        "SELECT * FROM movies WHERE id = ?",
        movie_id
    )

    if not movies:
        return redirect("/")

    movie = movies[0]

    if request.method == "POST":
        rating = request.form.get("rating")
        note = request.form.get("note")

        db.execute(
            """
            UPDATE movies
            SET rating = ?, note = ?
            WHERE id = ?
            """,
            rating,
            note,
            movie_id
        )

        return redirect(f"/movie/{movie_id}")

    return render_template("edit.html", movie=movie)


@app.route("/favorite/<int:movie_id>", methods=["POST"])
def favorite(movie_id):
    movies = db.execute(
        "SELECT favorite, status FROM movies WHERE id = ?",
        movie_id
    )

    if not movies:
        return redirect("/")

    movie = movies[0]
    new_value = 0 if movie["favorite"] else 1

    if new_value == 1:
        db.execute(
            """
            UPDATE movies
            SET favorite = 1,
                status = 'Watched',
                watched_date = DATE('now')
            WHERE id = ?
            """,
            movie_id
        )
    else:
        db.execute(
            "UPDATE movies SET favorite = 0 WHERE id = ?",
            movie_id
        )

    return redirect("/")

@app.route("/status/<int:movie_id>", methods=["POST"])
def change_status(movie_id):
    movies = db.execute(
        "SELECT status FROM movies WHERE id = ?",
        movie_id
    )

    if not movies:
        return redirect("/")

    movie = movies[0]

    if movie["status"] == "Watchlist":
        db.execute(
            """
            UPDATE movies
            SET status = ?, watched_date = DATE('now')
            WHERE id = ?
            """,
            "Watched",
            movie_id
        )
    else:
        db.execute(
            """
            UPDATE movies
            SET status = ?, watched_date = NULL
            WHERE id = ?
            """,
            "Watchlist",
            movie_id
        )

    return redirect("/")


@app.route("/delete/<int:movie_id>", methods=["POST"])
def delete(movie_id):
    db.execute(
        "DELETE FROM movies WHERE id = ?",
        movie_id
    )

    return redirect("/")


@app.route("/movie/<int:movie_id>")
def movie(movie_id):
    movies = db.execute(
        """
        SELECT movies.*, movie_catalog.tmdb_id
        FROM movies
        LEFT JOIN movie_catalog
        ON movies.catalog_id = movie_catalog.id
        WHERE movies.id = ?
        """,
        movie_id
    )

    if not movies:
        return redirect("/")

    movie = movies[0]
    tmdb = get_tmdb_details(movie["tmdb_id"])

    return render_template("movie.html", movie=movie, tmdb=tmdb)
@app.route("/catalog_movie/<int:catalog_id>")
def catalog_movie(catalog_id):
    movies = db.execute(
        "SELECT * FROM movie_catalog WHERE id = ?",
        catalog_id
    )

    if not movies:
        return redirect("/search")

    movie = movies[0]
    tmdb = get_tmdb_details(movie["tmdb_id"])

    existing = db.execute(
        "SELECT id, status, favorite FROM movies WHERE catalog_id = ?",
        catalog_id
    )

    return render_template(
        "catalog_movie.html",
        movie=movie,
        tmdb=tmdb,
        existing=existing
    )
