from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import uuid
import sqlite3
import json
import os
import re
from datetime import datetime, timedelta
from functools import wraps
import secrets
import random
import string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pixelcraft-secret-key-2024-rio-' + secrets.token_hex(16)
app.config['DATABASE'] = 'instance/pixelcraft.db'
app.config['UPLOAD_FOLDER'] = 'static/img/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'customer_login'

# Configurações de upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = (1920, 1080)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def resize_image(image_path, max_size=MAX_IMAGE_SIZE):
    try:
        with Image.open(image_path) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.save(image_path, optimize=True, quality=85)
    except Exception as e:
        print(f"Erro ao redimensionar: {e}")

# Database helper functions
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

# User classes for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, role, name=None):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.name = name or username
        self.is_admin = role == 'admin'
        self.is_customer = role == 'customer'

@login_manager.user_loader
def load_user(user_id):
    # Try admin users first
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
    if user:
        return User(f"admin_{user['id']}", user['username'], user['email'], 'admin')
    
    # Try customers
    customer = query_db('SELECT * FROM customers WHERE id = ?', [user_id], one=True)
    if customer:
        return User(f"customer_{customer['id']}", customer['email'], customer['email'], 'customer', customer['name'])
    
    return None

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Acesso negado. Área administrativa.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def customer_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_customer:
            flash('Acesso negado. Área de clientes.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize database
def init_db():
    db = get_db()
    
    # Create tables if they don't exist
    db.executescript('''
        -- Admin users table
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            active INTEGER DEFAULT 1,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Customers table
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            cpf TEXT,
            phone TEXT,
            birth_date DATE,
            address_street TEXT,
            address_number TEXT,
            address_complement TEXT,
            address_neighborhood TEXT,
            address_city TEXT,
            address_state TEXT,
            address_cep TEXT,
            newsletter INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Categories table
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            icon TEXT,
            color TEXT,
            ordem INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- PCs table
        CREATE TABLE IF NOT EXISTS pcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            subtitle TEXT,
            description TEXT,
            category_id INTEGER,
            price REAL NOT NULL,
            price_old REAL,
            main_image TEXT,
            gallery TEXT,
            processor TEXT,
            gpu TEXT,
            ram TEXT,
            storage TEXT,
            motherboard TEXT,
            psu TEXT,
            case_model TEXT,
            cooling TEXT,
            graffiti_artist TEXT,
            graffiti_style TEXT,
            graffiti_description TEXT,
            setup_price REAL DEFAULT 150,
            featured INTEGER DEFAULT 0,
            bestseller INTEGER DEFAULT 0,
            limited_edition INTEGER DEFAULT 0,
            pre_order INTEGER DEFAULT 0,
            in_stock INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            views INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        
        -- Orders table
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            customer_name TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            customer_cpf TEXT,
            delivery_street TEXT,
            delivery_number TEXT,
            delivery_complement TEXT,
            delivery_neighborhood TEXT,
            delivery_city TEXT,
            delivery_state TEXT,
            delivery_cep TEXT,
            items TEXT NOT NULL,
            subtotal REAL NOT NULL,
            shipping REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            total REAL NOT NULL,
            payment_method TEXT,
            payment_status TEXT DEFAULT 'pending',
            order_status TEXT DEFAULT 'pending',
            setup_service INTEGER DEFAULT 0,
            notes TEXT,
            tracking_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
        
        -- Games table
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            genre TEXT,
            publisher TEXT,
            release_year INTEGER,
            image_url TEXT,
            min_requirements TEXT,
            rec_requirements TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- PC Games relationship
        CREATE TABLE IF NOT EXISTS pc_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pc_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            performance TEXT,
            fps_avg INTEGER,
            resolution TEXT,
            settings TEXT,
            FOREIGN KEY (pc_id) REFERENCES pcs(id),
            FOREIGN KEY (game_id) REFERENCES games(id)
        );
        
        -- Reviews table
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pc_id INTEGER NOT NULL,
            customer_id INTEGER,
            order_id INTEGER,
            rating INTEGER NOT NULL,
            title TEXT,
            comment TEXT,
            verified_purchase INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pc_id) REFERENCES pcs(id),
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );
        
        -- Payment methods table
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            card_last4 TEXT,
            card_brand TEXT,
            card_holder TEXT,
            pix_key TEXT,
            is_default INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
        
        -- Newsletter subscribers
        CREATE TABLE IF NOT EXISTS newsletter (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    # Insert default admin user if not exists
    admin = query_db('SELECT * FROM users WHERE username = ?', ['admin'], one=True)
    if not admin:
        password_hash = generate_password_hash('admin123')
        db.execute('INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                  ['admin', 'admin@pixelcraft.com', password_hash, 'admin'])
    
    # Insert default categories if not exist
    categories_count = db.execute('SELECT COUNT(*) FROM categories').fetchone()[0]
    if categories_count == 0:
        default_categories = [
            ('Starter', 'starter', 'PCs para iniciantes no mundo gamer', 'gamepad', '#10B981', 1),
            ('Pro Gamer', 'pro-gamer', 'Alta performance para competitivos', 'trophy', '#8B5CF6', 2),
            ('Creator', 'creator', 'Para streamers e criadores de conteúdo', 'video', '#EC4899', 3),
            ('Ultra', 'ultra', 'O máximo em performance', 'crown', '#F59E0B', 4),
            ('Limited Edition', 'limited-edition', 'Edições exclusivas e únicas', 'star', '#EF4444', 5)
        ]
        for cat in default_categories:
            db.execute('INSERT INTO categories (name, slug, description, icon, color, ordem) VALUES (?, ?, ?, ?, ?, ?)', cat)
    
    # Insert sample PCs if not exist
    pcs_count = db.execute('SELECT COUNT(*) FROM pcs').fetchone()[0]
    if pcs_count == 0:
        sample_pcs = [
            ('Starter RJ', 'starter-rj', 'Perfeito para começar', 1, 2999.90, None, '/static/img/pcs/starter-rj.svg', 
             'AMD Ryzen 5 5600', 'RTX 3060 12GB', '16GB DDR4 3200MHz', '512GB NVMe SSD', 1, 0, 0, 1),
            ('Cristo Ultra', 'cristo-ultra', 'Performance divina', 4, 12999.90, 14999.90, '/static/img/pcs/cristo-ultra.svg',
             'Intel i9-13900K', 'RTX 4090 24GB', '64GB DDR5 6000MHz', '2TB NVMe Gen5', 1, 1, 0, 1),
            ('Ipanema Beast', 'ipanema-beast', 'Para os mais exigentes', 2, 7999.90, None, '/static/img/pcs/ipanema-beast.svg',
             'AMD Ryzen 7 7700X', 'RTX 4070 Ti 16GB', '32GB DDR5 5600MHz', '1TB NVMe SSD', 1, 1, 0, 1),
            ('Lapa Creator', 'lapa-creator', 'Streaming sem limites', 3, 9499.90, 10999.90, '/static/img/pcs/lapa-creator.svg',
             'Intel i7-13700K', 'RTX 4070 Ti Super', '32GB DDR5 RGB', '2TB NVMe + 4TB HDD', 1, 0, 0, 1)
        ]
        for pc in sample_pcs:
            db.execute('''INSERT INTO pcs (name, slug, subtitle, category_id, price, price_old, main_image,
                         processor, gpu, ram, storage, featured, bestseller, limited_edition, in_stock)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', pc)
    
    # Insert sample games if not exist
    games_count = db.execute('SELECT COUNT(*) FROM games').fetchone()[0]
    if games_count == 0:
        sample_games = [
            ('Counter-Strike 2', 'cs2', 'FPS', 'Valve', 2023, '/static/img/games/cs2.svg'),
            ('Valorant', 'valorant', 'FPS', 'Riot Games', 2020, '/static/img/games/valorant.svg'),
            ('League of Legends', 'lol', 'MOBA', 'Riot Games', 2009, '/static/img/games/lol.svg'),
            ('Fortnite', 'fortnite', 'Battle Royale', 'Epic Games', 2017, '/static/img/games/fortnite.svg'),
            ('GTA V', 'gta5', 'Action', 'Rockstar', 2013, '/static/img/games/gta5.svg'),
            ('Minecraft', 'minecraft', 'Sandbox', 'Mojang', 2011, '/static/img/games/minecraft.svg'),
            ('Cyberpunk 2077', 'cyberpunk', 'RPG', 'CD Projekt', 2020, '/static/img/games/cyberpunk.svg'),
            ('Red Dead Redemption 2', 'rdr2', 'Action', 'Rockstar', 2018, '/static/img/games/rdr2.svg')
        ]
        for game in sample_games:
            db.execute('INSERT INTO games (name, slug, genre, publisher, release_year, image_url) VALUES (?, ?, ?, ?, ?, ?)', game)
    
    db.commit()
    db.close()

# Routes - Public Pages
@app.route('/')
def index():
    featured_query = """
        SELECT p.*, c.name as category_name, c.color as category_color
        FROM pcs p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.active = 1 AND p.featured = 1
        ORDER BY p.created_at DESC
        LIMIT 8
    """
    featured_pcs = query_db(featured_query)
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    return render_template('index.html', featured_pcs=featured_pcs, categories=categories)

@app.route('/pcs')
def catalog():
    category = request.args.get('category')
    sort = request.args.get('sort', 'newest')
    price_min = request.args.get('price_min', type=int)
    price_max = request.args.get('price_max', type=int)
    
    base_query = """
        SELECT p.*, c.name as category_name, c.color as category_color
        FROM pcs p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.active = 1
    """
    params = []
    
    if category:
        base_query += ' AND c.slug = ?'
        params.append(category)
    
    if price_min:
        base_query += ' AND p.price >= ?'
        params.append(price_min)
    
    if price_max:
        base_query += ' AND p.price <= ?'
        params.append(price_max)
    
    # Sorting
    if sort == 'price_low':
        base_query += ' ORDER BY p.price ASC'
    elif sort == 'price_high':
        base_query += ' ORDER BY p.price DESC'
    elif sort == 'popular':
        base_query += ' ORDER BY p.views DESC'
    else:
        base_query += ' ORDER BY p.created_at DESC'
    
    pcs = query_db(base_query, params)
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    
    return render_template('catalog.html', pcs=pcs, categories=categories, current_category=category)

@app.route('/pc/<slug>')
def product_detail(slug):
    pc_query = """
        SELECT p.*, c.name as category_name, c.color as category_color
        FROM pcs p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.slug = ? AND p.active = 1
    """
    pc = query_db(pc_query, [slug], one=True)
    
    if not pc:
        flash('Produto não encontrado', 'error')
        return redirect(url_for('catalog'))
    
    execute_db('UPDATE pcs SET views = views + 1 WHERE id = ?', [pc['id']])
    
    games_query = """
        SELECT g.*, pg.performance, pg.fps_avg, pg.resolution
        FROM games g
        JOIN pc_games pg ON g.id = pg.game_id
        WHERE pg.pc_id = ?
        ORDER BY pg.performance DESC
    """
    games = query_db(games_query, [pc['id']])
    
    reviews_query = """
        SELECT r.*, c.name as customer_name
        FROM reviews r
        LEFT JOIN customers c ON r.customer_id = c.id
        WHERE r.pc_id = ? AND r.status = 'approved'
        ORDER BY r.created_at DESC
        LIMIT 10
    """
    reviews = query_db(reviews_query, [pc['id']])
    
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

# Customer Authentication
@app.route('/login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        customer = query_db('SELECT * FROM customers WHERE email = ? AND active = 1', [email], one=True)
        
        if customer and check_password_hash(customer['password_hash'], password):
            user_obj = User(f"customer_{customer['id']}", customer['email'], customer['email'], 'customer', customer['name'])
            login_user(user_obj)
            execute_db('UPDATE customers SET last_login = ? WHERE id = ?', [datetime.now(), customer['id']])
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('customer_dashboard'))
        
        flash('E-mail ou senha inválidos', 'error')
    
    return render_template('customer/login.html')

@app.route('/register', methods=['GET', 'POST'])
def customer_register():
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'cpf': request.form.get('cpf'),
            'phone': request.form.get('phone'),
            'newsletter': 1 if request.form.get('newsletter') else 0
        }
        
        # Check if email already exists
        existing = query_db('SELECT id FROM customers WHERE email = ?', [data['email']], one=True)
        if existing:
            flash('E-mail já cadastrado', 'error')
            return render_template('customer/register.html', data=data)
        
        # Create customer
        try:
            password_hash = generate_password_hash(data['password'])
            customer_id = execute_db('''
                INSERT INTO customers (name, email, password_hash, cpf, phone, newsletter)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', [data['name'], data['email'], password_hash, data['cpf'], data['phone'], data['newsletter']])
            
            # Auto login
            user_obj = User(f"customer_{customer_id}", data['email'], data['email'], 'customer', data['name'])
            login_user(user_obj)
            
            flash('Conta criada com sucesso! Bem-vindo ao PixelCraft PC!', 'success')
            return redirect(url_for('customer_dashboard'))
            
        except Exception as e:
            flash(f'Erro ao criar conta: {str(e)}', 'error')
    
    return render_template('customer/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta', 'info')
    return redirect(url_for('index'))

# Customer Area
@app.route('/minha-conta')
@customer_required
def customer_dashboard():
    customer_id = current_user.id.replace('customer_', '')
    
    # Get customer data
    customer = query_db('SELECT * FROM customers WHERE id = ?', [customer_id], one=True)
    
    # Get recent orders
    orders = query_db('''
        SELECT * FROM orders 
        WHERE customer_id = ? 
        ORDER BY created_at DESC 
        LIMIT 5
    ''', [customer_id])
    
    # Get stats
    stats = {
        'total_orders': query_db('SELECT COUNT(*) as count FROM orders WHERE customer_id = ?', 
                                [customer_id], one=True)['count'],
        'total_spent': query_db('SELECT SUM(total) as total FROM orders WHERE customer_id = ? AND payment_status = "completed"', 
                               [customer_id], one=True)['total'] or 0
    }
    
    return render_template('customer/dashboard.html', customer=customer, orders=orders, stats=stats)

@app.route('/minha-conta/pedidos')
@customer_required
def customer_orders():
    customer_id = current_user.id.replace('customer_', '')
    
    orders = query_db('''
        SELECT * FROM orders 
        WHERE customer_id = ? 
        ORDER BY created_at DESC
    ''', [customer_id])
    
    return render_template('customer/orders.html', orders=orders)

@app.route('/minha-conta/pedido/<order_number>')
@customer_required
def customer_order_detail(order_number):
    customer_id = current_user.id.replace('customer_', '')
    
    order = query_db('''
        SELECT * FROM orders 
        WHERE customer_id = ? AND order_number = ?
    ''', [customer_id, order_number], one=True)
    
    if not order:
        flash('Pedido não encontrado', 'error')
        return redirect(url_for('customer_orders'))
    
    # Parse items JSON
    try:
        items = json.loads(order['items'])
    except:
        items = []
    
    return render_template('customer/order_detail.html', order=order, items=items)

@app.route('/minha-conta/perfil', methods=['GET', 'POST'])
@customer_required
def customer_profile():
    customer_id = current_user.id.replace('customer_', '')
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'cpf': request.form.get('cpf'),
            'phone': request.form.get('phone'),
            'birth_date': request.form.get('birth_date'),
            'newsletter': 1 if request.form.get('newsletter') else 0
        }
        
        # Update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            current_password = request.form.get('current_password')
            customer = query_db('SELECT password_hash FROM customers WHERE id = ?', [customer_id], one=True)
            
            if not check_password_hash(customer['password_hash'], current_password):
                flash('Senha atual incorreta', 'error')
                return redirect(url_for('customer_profile'))
            
            data['password_hash'] = generate_password_hash(new_password)
        
        # Update customer
        try:
            if 'password_hash' in data:
                execute_db('''
                    UPDATE customers SET 
                    name=?, email=?, cpf=?, phone=?, birth_date=?, newsletter=?, password_hash=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                ''', [data['name'], data['email'], data['cpf'], data['phone'], data['birth_date'], 
                     data['newsletter'], data['password_hash'], customer_id])
            else:
                execute_db('''
                    UPDATE customers SET 
                    name=?, email=?, cpf=?, phone=?, birth_date=?, newsletter=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                ''', [data['name'], data['email'], data['cpf'], data['phone'], data['birth_date'], 
                     data['newsletter'], customer_id])
            
            flash('Perfil atualizado com sucesso!', 'success')
            
        except Exception as e:
            flash(f'Erro ao atualizar perfil: {str(e)}', 'error')
    
    customer = query_db('SELECT * FROM customers WHERE id = ?', [customer_id], one=True)
    return render_template('customer/profile.html', customer=customer)

@app.route('/minha-conta/enderecos', methods=['GET', 'POST'])
@customer_required
def customer_addresses():
    customer_id = current_user.id.replace('customer_', '')
    
    if request.method == 'POST':
        data = {
            'address_cep': request.form.get('cep'),
            'address_street': request.form.get('street'),
            'address_number': request.form.get('number'),
            'address_complement': request.form.get('complement'),
            'address_neighborhood': request.form.get('neighborhood'),
            'address_city': request.form.get('city'),
            'address_state': request.form.get('state')
        }
        
        try:
            execute_db('''
                UPDATE customers SET 
                address_cep=?, address_street=?, address_number=?, address_complement=?,
                address_neighborhood=?, address_city=?, address_state=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', [data['address_cep'], data['address_street'], data['address_number'], 
                 data['address_complement'], data['address_neighborhood'], data['address_city'], 
                 data['address_state'], customer_id])
            
            flash('Endereço atualizado com sucesso!', 'success')
            
        except Exception as e:
            flash(f'Erro ao atualizar endereço: {str(e)}', 'error')
    
    customer = query_db('SELECT * FROM customers WHERE id = ?', [customer_id], one=True)
    return render_template('customer/addresses.html', customer=customer)

@app.route('/minha-conta/pagamentos')
@customer_required
def customer_payments():
    customer_id = current_user.id.replace('customer_', '')
    
    payment_methods = query_db('''
        SELECT * FROM payment_methods 
        WHERE customer_id = ? AND active = 1
        ORDER BY is_default DESC, created_at DESC
    ''', [customer_id])
    
    return render_template('customer/payments.html', payment_methods=payment_methods)

# Cart & Checkout
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
    
    for item in cart:
        if item['id'] == pc_id:
            item['quantity'] += 1
            session['cart'] = cart
            return jsonify({'success': True, 'cart_count': len(cart)})
    
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
    
    # If logged in, get customer data
    customer = None
    if current_user.is_authenticated and current_user.is_customer:
        customer_id = current_user.id.replace('customer_', '')
        customer = query_db('SELECT * FROM customers WHERE id = ?', [customer_id], one=True)
    
    return render_template('checkout.html', cart=cart, total=total, customer=customer)

@app.route('/process-order', methods=['POST'])
def process_order():
    cart = session.get('cart', [])
    if not cart:
        flash('Carrinho vazio', 'error')
        return redirect(url_for('catalog'))
    
    # Generate order number
    order_number = 'PC' + datetime.now().strftime('%Y%m%d') + ''.join(random.choices(string.digits, k=6))
    
    # Get customer data
    customer_id = None
    if current_user.is_authenticated and current_user.is_customer:
        customer_id = int(current_user.id.replace('customer_', ''))
    
    # Calculate totals
    subtotal = sum(item['price'] * item['quantity'] for item in cart)
    setup_service = 1 if request.form.get('setup_service') else 0
    setup_fee = 150 if setup_service else 0
    total = subtotal + setup_fee
    
    # Apply discount for PIX payment
    payment_method = request.form.get('payment', 'pix')
    if payment_method == 'pix':
        total = total * 0.95  # 5% discount
    
    # Create order
    try:
        order_id = execute_db('''
            INSERT INTO orders (
                order_number, customer_id, customer_name, customer_email, customer_phone, customer_cpf,
                delivery_street, delivery_number, delivery_complement, delivery_neighborhood,
                delivery_city, delivery_state, delivery_cep, items, subtotal, shipping,
                total, payment_method, setup_service
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            order_number, customer_id, request.form.get('name'), request.form.get('email'),
            request.form.get('phone'), request.form.get('cpf'), request.form.get('street'),
            request.form.get('number'), request.form.get('complement'), request.form.get('neighborhood'),
            request.form.get('city'), request.form.get('state'), request.form.get('cep'),
            json.dumps(cart), subtotal, 0, total, payment_method, setup_service
        ])
        
        # Clear cart
        session['cart'] = []
        
        flash(f'Pedido {order_number} criado com sucesso!', 'success')
        
        if current_user.is_authenticated:
            return redirect(url_for('customer_order_detail', order_number=order_number))
        else:
            return render_template('order_success.html', order_number=order_number, total=total, payment_method=payment_method)
        
    except Exception as e:
        flash(f'Erro ao processar pedido: {str(e)}', 'error')
        return redirect(url_for('checkout'))

# Admin Routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'total_pcs': query_db('SELECT COUNT(*) as count FROM pcs WHERE active = 1', one=True)['count'],
        'total_orders': query_db('SELECT COUNT(*) as count FROM orders', one=True)['count'],
        'total_customers': query_db('SELECT COUNT(*) as count FROM customers', one=True)['count'],
        'total_revenue': query_db('SELECT SUM(total) as total FROM orders WHERE payment_status = "completed"', one=True)['total'] or 0
    }
    
    recent_orders = query_db('''
        SELECT o.*, c.name as customer_name
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        ORDER BY o.created_at DESC
        LIMIT 10
    ''')
    
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = query_db('SELECT * FROM users WHERE username = ? AND active = 1', [username], one=True)
        
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(f"admin_{user['id']}", user['username'], user['email'], 'admin')
            login_user(user_obj)
            execute_db('UPDATE users SET last_login = ? WHERE id = ?', [datetime.now(), user['id']])
            return redirect(url_for('admin_dashboard'))
        
        flash('Usuário ou senha inválidos', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
@admin_required
def admin_logout():
    logout_user()
    return redirect(url_for('index'))

# Admin - Customers Management
@app.route('/admin/customers')
@admin_required
def admin_customers():
    search = request.args.get('search', '')
    
    if search:
        customers = query_db('''
            SELECT c.*, COUNT(DISTINCT o.id) as total_orders, SUM(o.total) as total_spent
            FROM customers c
            LEFT JOIN orders o ON c.id = o.customer_id
            WHERE c.name LIKE ? OR c.email LIKE ? OR c.cpf LIKE ?
            GROUP BY c.id
            ORDER BY c.created_at DESC
        ''', [f'%{search}%', f'%{search}%', f'%{search}%'])
    else:
        customers = query_db('''
            SELECT c.*, COUNT(DISTINCT o.id) as total_orders, SUM(o.total) as total_spent
            FROM customers c
            LEFT JOIN orders o ON c.id = o.customer_id
            GROUP BY c.id
            ORDER BY c.created_at DESC
        ''')
    
    return render_template('admin/customers.html', customers=customers, search=search)

@app.route('/admin/customer/<int:customer_id>')
@admin_required
def admin_customer_detail(customer_id):
    customer = query_db('SELECT * FROM customers WHERE id = ?', [customer_id], one=True)
    if not customer:
        flash('Cliente não encontrado', 'error')
        return redirect(url_for('admin_customers'))
    
    orders = query_db('SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC', [customer_id])
    
    stats = {
        'total_orders': len(orders),
        'total_spent': sum(order['total'] for order in orders if order['payment_status'] == 'completed'),
        'avg_order': sum(order['total'] for order in orders) / len(orders) if orders else 0
    }
    
    return render_template('admin/customer_detail.html', customer=customer, orders=orders, stats=stats)

# Admin - Orders Management
@app.route('/admin/orders')
@admin_required
def admin_orders():
    status_filter = request.args.get('status', '')
    
    if status_filter:
        orders = query_db('''
            SELECT o.*, c.name as customer_name
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            WHERE o.order_status = ?
            ORDER BY o.created_at DESC
        ''', [status_filter])
    else:
        orders = query_db('''
            SELECT o.*, c.name as customer_name
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            ORDER BY o.created_at DESC
        ''')
    
    return render_template('admin/orders.html', orders=orders, status_filter=status_filter)

@app.route('/admin/order/<order_number>')
@admin_required
def admin_order_detail(order_number):
    order = query_db('''
        SELECT o.*, c.name as customer_name, c.email as customer_email_full
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.order_number = ?
    ''', [order_number], one=True)
    
    if not order:
        flash('Pedido não encontrado', 'error')
        return redirect(url_for('admin_orders'))
    
    try:
        items = json.loads(order['items'])
    except:
        items = []
    
    return render_template('admin/order_detail.html', order=order, items=items)

@app.route('/admin/order/<order_number>/update-status', methods=['POST'])
@admin_required
def admin_update_order_status(order_number):
    new_status = request.form.get('status')
    payment_status = request.form.get('payment_status')
    tracking_code = request.form.get('tracking_code')
    
    try:
        execute_db('''
            UPDATE orders SET 
            order_status = ?, payment_status = ?, tracking_code = ?, updated_at = CURRENT_TIMESTAMP
            WHERE order_number = ?
        ''', [new_status, payment_status, tracking_code, order_number])
        
        flash('Status do pedido atualizado!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar pedido: {str(e)}', 'error')
    
    return redirect(url_for('admin_order_detail', order_number=order_number))

# Admin - Games Management
@app.route('/admin/games')
@admin_required
def admin_games():
    games = query_db('SELECT * FROM games ORDER BY name')
    return render_template('admin/games.html', games=games)

@app.route('/admin/game/new', methods=['GET', 'POST'])
@admin_required
def admin_game_new():
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'genre': request.form.get('genre'),
            'publisher': request.form.get('publisher'),
            'release_year': request.form.get('release_year'),
            'min_requirements': request.form.get('min_requirements'),
            'rec_requirements': request.form.get('rec_requirements')
        }
        
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', data['name'].lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        
        try:
            execute_db('''
                INSERT INTO games (name, slug, genre, publisher, release_year, min_requirements, rec_requirements)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [data['name'], slug, data['genre'], data['publisher'], data['release_year'],
                 data['min_requirements'], data['rec_requirements']])
            
            flash('Jogo adicionado com sucesso!', 'success')
            return redirect(url_for('admin_games'))
        except Exception as e:
            flash(f'Erro ao adicionar jogo: {str(e)}', 'error')
    
    return render_template('admin/game_form.html')

# API Routes
@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    results = query_db('''
        SELECT id, name, slug, price, main_image
        FROM pcs
        WHERE active = 1 AND (name LIKE ? OR description LIKE ?)
        LIMIT 10
    ''', [f'%{query}%', f'%{query}%'])
    
    return jsonify([dict(row) for row in results])

@app.route('/api/newsletter', methods=['POST'])
def api_newsletter():
    email = request.get_json().get('email')
    
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'E-mail inválido'}), 400
    
    try:
        execute_db('INSERT OR IGNORE INTO newsletter (email) VALUES (?)', [email])
        return jsonify({'success': True, 'message': 'E-mail cadastrado com sucesso!'})
    except:
        return jsonify({'success': False, 'message': 'Erro ao cadastrar e-mail'}), 500

# Template filters
@app.template_filter('currency')
def currency_filter(value):
    if value is None:
        return "0,00"
    return f"{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

@app.template_filter('json_loads')
def json_loads_filter(value):
    if value:
        try:
            return json.loads(value)
        except:
            return []
    return []

@app.template_filter('date_format')
def date_format(value):
    if value:
        try:
            dt = datetime.strptime(str(value)[:19], '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d/%m/%Y às %H:%M')
        except:
            return value
    return ''

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Initialize and run
if __name__ == '__main__':
    # Create instance directory if it doesn't exist
    os.makedirs('instance', exist_ok=True)
    os.makedirs('static/img/uploads', exist_ok=True)
    
    # Initialize database
    init_db()
    
    # Run app
    app.run(debug=True, host='0.0.0.0', port=5000)