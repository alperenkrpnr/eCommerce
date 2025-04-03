from flask import Flask, render_template, request, redirect, url_for, flash
from flask_pymongo import PyMongo
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from bson.objectid import ObjectId
import os, math
from datetime import datetime

# App and configuration
app = Flask(__name__)
app.config.from_pyfile('config.py')  # Load config.py

mongo = PyMongo(app)  # Initialize connection using Flask-PyMongo

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Define the User model
class User(UserMixin):
    def __init__(self, user):
        self.id = str(user['_id'])
        self.username = user['username']
        self.role = user.get('role', 'user')  # "admin" or "user"

@login_manager.user_loader
def load_user(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        return User(user)
    return None

# Home page: List products with search, sorting, filtering and dynamic pagination
@app.route('/')
def index():
    search = request.args.get('search', '')
    sort_by = request.args.get('sort_by', '')
    category = request.args.get('category', '')
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    page_size = 6

    query = {}
    if search:
        query['name'] = {'$regex': search, '$options': 'i'}
    if category:
        query['category'] = category

    # Get total number of products
    total_items = mongo.db.items.count_documents(query)
    total_pages = math.ceil(total_items / page_size)

    cursor = mongo.db.items.find(query)

    # Sorting options
    if sort_by == 'price':
        cursor = cursor.sort('price', 1)
    elif sort_by == 'rating':
        cursor = cursor.sort('rating', -1)

    # Pagination: skip & limit
    cursor = cursor.skip((page - 1) * page_size).limit(page_size)
    items = list(cursor)

    return render_template('index.html', items=items, page=page, total_pages=total_pages, 
                           search=search, sort_by=sort_by, category=category)

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = mongo.db.users.find_one({'username': username, 'password': password})
        if user:
            user_obj = User(user)
            login_user(user_obj)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Incorrect username or password.', 'danger')
    return render_template('login.html')

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('index'))

# Register page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        new_user = {
            "username": request.form.get('username'),
            "password": request.form.get('password'),
            "role": "user",  # Default role is user
            "given_ratings": [],
            "given_reviews": []
        }
        mongo.db.users.insert_one(new_user)
        flash('Registration successful, please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# Admin dashboard (accessible only to admin)
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('index'))
    items = list(mongo.db.items.find())
    users = list(mongo.db.users.find())
    return render_template('admin_dashboard.html', items=items, users=users)

# Admin: Add new product page
@app.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        item = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "price": float(request.form.get("price")),
            "seller": request.form.get("seller"),
            "category": request.form.get("category"),
            "image": request.form.get("image"),
            "battery_life": request.form.get("battery_life"),
            "age": request.form.get("age"),
            "size": request.form.get("size"),
            "material": request.form.get("material"),
            "rating": 0,
            "ratings": [],
            "reviews": []
        }
        mongo.db.items.insert_one(item)
        flash('Product added successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_item.html')

# Admin: Remove product (direct removal without confirmation)
@app.route('/remove_item/<item_id>', methods=['POST'])
@login_required
def remove_item(item_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('index'))
    mongo.db.items.delete_one({"_id": ObjectId(item_id)})
    flash('Product removed.', 'success')
    return redirect(url_for('admin_dashboard'))

# Admin: Add new user page
@app.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        new_user = {
            "username": request.form.get('username'),
            "password": request.form.get('password'),
            "role": request.form.get('role', 'user'),
            "given_ratings": [],
            "given_reviews": []
        }
        mongo.db.users.insert_one(new_user)
        flash('User added successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_user.html')

# Admin: Remove user (direct removal without confirmation)
@app.route('/remove_user/<user_id>', methods=['POST'])
@login_required
def remove_user(user_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('index'))
    user_to_remove = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if user_to_remove:
        username = user_to_remove['username']
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})
        mongo.db.items.update_many({}, {"$pull": {"reviews": {"user": username}}})
        flash('User removed.', 'success')
    else:
        flash('User not found.', 'danger')
    return redirect(url_for('admin_dashboard'))

# Product Detail Page: Add/update rating and review
@app.route('/item/<item_id>', methods=['GET', 'POST'])
def item_detail(item_id):
    item = mongo.db.items.find_one({"_id": ObjectId(item_id)})
    
    # Get related products from the same category (limited to 4)
    related_products = list(mongo.db.items.find(
        {"category": item["category"], "_id": {"$ne": ObjectId(item_id)}}
    ).limit(4))
    
    if request.method == 'POST':
        if current_user.is_authenticated:
            rating = int(request.form.get("rating"))
            review = request.form.get("review")
            
            # Update product ratings: Remove previous rating by this user, then add new rating
            mongo.db.items.update_one(
                {"_id": ObjectId(item_id)},
                {"$pull": {"ratings": {"user_id": current_user.id}}}
            )
            mongo.db.items.update_one(
                {"_id": ObjectId(item_id)},
                {"$push": {"ratings": {"user_id": current_user.id, "rating": rating}}}
            )
            
            # Recalculate average rating
            updated_item = mongo.db.items.find_one({"_id": ObjectId(item_id)})
            all_ratings = [r["rating"] for r in updated_item.get("ratings", [])]
            avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 0
            mongo.db.items.update_one(
                {"_id": ObjectId(item_id)},
                {"$set": {"rating": avg_rating}}
            )
            
            # Update product reviews: Remove previous review by this user, then add new review (with rating)
            mongo.db.items.update_one(
                {"_id": ObjectId(item_id)},
                {"$pull": {"reviews": {"user": current_user.username}}}
            )
            mongo.db.items.update_one(
                {"_id": ObjectId(item_id)},
                {"$push": {"reviews": {"user": current_user.username, "review": review, "rating": rating, "date": datetime.now()}}}
            )
            
            # Update user's document with given rating and review (including product name)
            mongo.db.users.update_one(
                {"_id": ObjectId(current_user.id)},
                {"$pull": {"given_ratings": {"item_id": item_id}}}
            )
            mongo.db.users.update_one(
                {"_id": ObjectId(current_user.id)},
                {"$push": {"given_ratings": {"item_id": item_id, "rating": rating}}}
            )
            mongo.db.users.update_one(
                {"_id": ObjectId(current_user.id)},
                {"$pull": {"given_reviews": {"item_id": item_id}}}
            )
            mongo.db.users.update_one(
                {"_id": ObjectId(current_user.id)},
                {"$push": {"given_reviews": {"item_id": item_id, "item_name": item["name"], "review": review, "rating": rating, "date": datetime.now()}}}
            )
            
            flash('Review updated successfully.', 'success')
        else:
            flash('You need to be logged in to submit a review.', 'danger')
        return redirect(url_for('item_detail', item_id=item_id))
    
    return render_template('item_detail.html', item=item, related_products=related_products)

# User Profile Page: Show given ratings and reviews
@app.route('/profile')
@login_required
def user_profile():
    user_doc = mongo.db.users.find_one({"_id": ObjectId(current_user.id)})
    
    # Get user ratings
    ratings = []
    for rating_obj in user_doc.get("given_ratings", []):
        if isinstance(rating_obj, dict) and "rating" in rating_obj:
            ratings.append(rating_obj["rating"])
    
    # Calculate average rating
    avg_rating = sum(ratings) / len(ratings) if ratings else None
    
    # Get user reviews
    reviews = user_doc.get("given_reviews", [])
    
    # Check date field - mark those without date
    for review in reviews:
        if "date" not in review:
            review["date"] = None
    
    return render_template('user_profile.html', user=user_doc, average_rating=avg_rating, reviews=reviews)

if __name__ == '__main__':
    app.run(debug=True)