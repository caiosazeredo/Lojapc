from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import json
import os
from datetime import datetime, timedelta
from functools import wraps
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pixelcraft-secret-key-2024-rio'
app.config['DATABASE'] = 'instance/pixelcraft.db'
app.config['UPLOAD_FOLDER'] = 'static/img/pcs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

# Database helper
def get_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    db.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    lastrowid = cur.lastrowid
    db.close()
    return lastrowid

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, role):
        self.id = id
        self.username = username
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
    if user:
        return User(user['id'], user['username'], user['email'], user['role'])
    return None

# Routes - Home
@app.route('/')
def index():
    query = """
        SELECT p.*, c.name as category_name, c.color as category_color
        FROM pcs p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.active = 1 AND p.featured = 1
        ORDER BY p.created_at DESC
        LIMIT 8
    """
    featured_pcs = query_db(query)
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    return render_template('index.html', featured_pcs=featured_pcs, categories=categories)

# Routes - Catalog
@app.route('/pcs')
def catalog():
    category = request.args.get('category')
    sort = request.args.get('sort', 'newest')
    price_min = request.args.get('price_min', type=int)
    price_max = request.args.get('price_max', type=int)
    
    query = """
        SELECT p.*, c.name as category_name, c.color as category_color
        FROM pcs p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.active = 1
    """
    params = []
    
    if category:
        query += ' AND c.slug = ?'
        params.append(category)
    
    if price_min:
        query += ' AND p.price >= ?'
        params.append(price_min)
    
    if price_max:
        query += ' AND p.price <= ?'
        params.append(price_max)
    
    # Sorting
    if sort == 'price_low':
        query += ' ORDER BY p.price ASC'
    elif sort == 'price_high':
        query += ' ORDER BY p.price DESC'
    elif sort == 'popular':
        query += ' ORDER BY p.views DESC'
    else:  # newest
        query += ' ORDER BY p.created_at DESC'
    
    pcs = query_db(query, params)
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    
    return render_template('catalog.html', pcs=pcs, categories=categories, current_category=category)

# Routes - Product Detail
@app.route('/pc/<slug>')
def product_detail(slug):
    query = """
        SELECT p.*, c.name as category_name, c.color as category_color
        FROM pcs p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.slug = ? AND p.active = 1
    """
    pc = query_db(query, [slug], one=True)
    
    if not pc:
        flash('Produto não encontrado', 'error')
        return redirect(url_for('catalog'))
    
    # Update views
    execute_db('UPDATE pcs SET views = views + 1 WHERE id = ?', [pc['id']])
    
    # Get games this PC can run
    games_query = """
        SELECT g.*, pg.performance, pg.fps_avg, pg.resolution
        FROM games g
        JOIN pc_games pg ON g.id = pg.game_id
        WHERE pg.pc_id = ?
        ORDER BY pg.performance DESC
    """
    games = query_db(games_query, [pc['id']])
    
    # Get reviews
    reviews_query = """
        SELECT r.*, c.name as customer_name
        FROM reviews r
        LEFT JOIN customers c ON r.customer_id = c.id
        WHERE r.pc_id = ? AND r.status = 'approved'
        ORDER BY r.created_at DESC
        LIMIT 10
    """
    reviews = query_db(reviews_query, [pc['id']])
    
    # Related products
    related_query = """
        SELECT p.*, c.name as category_name, c.color as category_color
        FROM pcs p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.category_id = ? AND p.id != ? AND p.active = 1
        ORDER BY RANDOM()
        LIMIT 4
    """
    related = query_db(related_query, [pc['category_id'], pc['id']])
    
    return render_template('product.html', pc=pc, games=games, reviews=reviews, related=related)

# Routes - Cart & Checkout
@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    pc_id = data.get('pc_id')
    
    pc = query_db('SELECT * FROM pcs WHERE id = ? AND active = 1', [pc_id], one=True)
    if not pc:
        return jsonify({'error': 'Produto não encontrado'}), 404
    
    cart = session.get('cart', [])
    
    # Check if already in cart
    for item in cart:
        if item['id'] == pc_id:
            item['quantity'] += 1
            session['cart'] = cart
            return jsonify({'success': True, 'cart_count': len(cart)})
    
    # Add new item
    cart.append({
        'id': pc['id'],
        'name': pc['name'],
        'price': float(pc['price']),
        'image': pc['main_image'],
        'quantity': 1
    })
    
    session['cart'] = cart
    return jsonify({'success': True, 'cart_count': len(cart)})

@app.route('/checkout')
def checkout():
    cart = session.get('cart', [])
    if not cart:
        flash('Seu carrinho está vazio', 'warning')
        return redirect(url_for('catalog'))
    
    total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template('checkout.html', cart=cart, total=total)

# Admin Routes
@app.route('/admin')
@login_required
def admin_dashboard():
    stats = {
        'total_pcs': query_db('SELECT COUNT(*) as count FROM pcs WHERE active = 1', one=True)['count'],
        'total_orders': query_db('SELECT COUNT(*) as count FROM orders', one=True)['count'],
        'total_customers': query_db('SELECT COUNT(*) as count FROM customers', one=True)['count'],
        'total_revenue': query_db('SELECT SUM(total) as total FROM orders WHERE payment_status = "completed"', one=True)['total'] or 0
    }
    
    recent_orders_query = """
        SELECT o.*, c.name as customer_name
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        ORDER BY o.created_at DESC
        LIMIT 10
    """
    recent_orders = query_db(recent_orders_query)
    
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = query_db('SELECT * FROM users WHERE username = ? AND active = 1', [username], one=True)
        
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], user['username'], user['email'], user['role'])
            login_user(user_obj)
            
            # Update last login
            execute_db('UPDATE users SET last_login = ? WHERE id = ?', [datetime.now(), user['id']])
            
            return redirect(url_for('admin_dashboard'))
        
        flash('Usuário ou senha inválidos', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('index'))

# Template filters
@app.template_filter('currency')
def currency_filter(value):
    return f"{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

@app.template_filter('json_loads')
def json_loads_filter(value):
    if value:
        return json.loads(value)
    return []

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# Rotas Admin adicionais
@app.route('/admin/pcs')
@login_required
def admin_pcs():
    query = '''
        SELECT p.*, c.name as category_name
        FROM pcs p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.created_at DESC
    '''
    pcs = query_db(query)
    return render_template('admin/pcs.html', pcs=pcs)

@app.route('/admin/games')
@login_required
def admin_games():
    games = query_db('SELECT * FROM games ORDER BY created_at DESC')
    return render_template('admin/games.html', games=games)

@app.route('/admin/orders')
@login_required
def admin_orders():
    query = '''
        SELECT o.*, c.name as customer_name
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        ORDER BY o.created_at DESC
    '''
    orders = query_db(query)
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/customers')
@login_required
def admin_customers():
    customers = query_db('SELECT * FROM customers ORDER BY created_at DESC')
    return render_template('admin/customers.html', customers=customers)

@app.route('/admin/settings')
@login_required
def admin_settings():
    return render_template('admin/settings.html')

@app.route('/admin/pc/new')
@login_required
def admin_pc_new():
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    return render_template('admin/pc_form.html', categories=categories)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
