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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pixelcraft-secret-key-2024-rio'
app.config['DATABASE'] = 'instance/pixelcraft.db'
app.config['UPLOAD_FOLDER'] = 'static/img/pcs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

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
    featured_query = "SELECT p.*, c.name as category_name, c.color as category_color FROM pcs p LEFT JOIN categories c ON p.category_id = c.id WHERE p.active = 1 AND p.featured = 1 ORDER BY p.created_at DESC LIMIT 8"
    featured_pcs = query_db(featured_query)
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    return render_template('index.html', featured_pcs=featured_pcs, categories=categories)

# Routes - Catalog
@app.route('/pcs')
def catalog():
    category = request.args.get('category')
    sort = request.args.get('sort', 'newest')
    price_min = request.args.get('price_min', type=int)
    price_max = request.args.get('price_max', type=int)
    
    base_query = "SELECT p.*, c.name as category_name, c.color as category_color FROM pcs p LEFT JOIN categories c ON p.category_id = c.id WHERE p.active = 1"
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
    else:  # newest
        base_query += ' ORDER BY p.created_at DESC'
    
    pcs = query_db(base_query, params)
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    
    return render_template('catalog.html', pcs=pcs, categories=categories, current_category=category)

# Routes - Product Detail
@app.route('/pc/<slug>')
def product_detail(slug):
    pc_query = "SELECT p.*, c.name as category_name, c.color as category_color FROM pcs p LEFT JOIN categories c ON p.category_id = c.id WHERE p.slug = ? AND p.active = 1"
    pc = query_db(pc_query, [slug], one=True)
    
    if not pc:
        flash('Produto não encontrado', 'error')
        return redirect(url_for('catalog'))
    
    # Update views
    execute_db('UPDATE pcs SET views = views + 1 WHERE id = ?', [pc['id']])
    
    # Get games this PC can run
    games_query = "SELECT g.*, pg.performance, pg.fps_avg, pg.resolution FROM games g JOIN pc_games pg ON g.id = pg.game_id WHERE pg.pc_id = ? ORDER BY pg.performance DESC"
    games = query_db(games_query, [pc['id']])
    
    # Get reviews
    reviews_query = "SELECT r.*, c.name as customer_name FROM reviews r LEFT JOIN customers c ON r.customer_id = c.id WHERE r.pc_id = ? AND r.status = 'approved' ORDER BY r.created_at DESC LIMIT 10"
    reviews = query_db(reviews_query, [pc['id']])
    
    # Related products
    related_query = "SELECT p.*, c.name as category_name, c.color as category_color FROM pcs p LEFT JOIN categories c ON p.category_id = c.id WHERE p.category_id = ? AND p.id != ? AND p.active = 1 ORDER BY RANDOM() LIMIT 4"
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

@app.route('/admin/upload-image', methods=['POST'])
@login_required
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    if file and allowed_file(file.filename):
        # Gerar nome único
        filename = f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Criar diretório se não existir
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Salvar arquivo
        file.save(filepath)
        
        # Redimensionar se necessário
        resize_image(filepath)
        
        # Retornar URL da imagem
        image_url = f"/static/img/pcs/{filename}"
        return jsonify({'success': True, 'url': image_url, 'filename': filename})
    
    return jsonify({'error': 'Tipo de arquivo não permitido'}), 400

@app.route('/admin/delete-image', methods=['POST'])
@login_required
def delete_image():
    data = request.get_json()
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'error': 'Nome do arquivo não fornecido'}), 400
    
    # Verificar se arquivo existe
    if filename.startswith('/static/img/pcs/'):
        filename = filename.replace('/static/img/pcs/', '')
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': f'Erro ao excluir arquivo: {str(e)}'}), 500
    
    return jsonify({'error': 'Arquivo não encontrado'}), 404

@app.route('/admin')
@login_required
def admin_dashboard():
    stats = {
        'total_pcs': query_db('SELECT COUNT(*) as count FROM pcs WHERE active = 1', one=True)['count'],
        'total_orders': query_db('SELECT COUNT(*) as count FROM orders', one=True)['count'],
        'total_customers': query_db('SELECT COUNT(*) as count FROM customers', one=True)['count'],
        'total_revenue': query_db('SELECT SUM(total) as total FROM orders WHERE payment_status = "completed"', one=True)['total'] or 0
    }
    
    recent_orders_query = "SELECT o.*, c.name as customer_name FROM orders o LEFT JOIN customers c ON o.customer_id = c.id ORDER BY o.created_at DESC LIMIT 10"
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

# Admin - PCs
@app.route('/admin/pcs')
@login_required
def admin_pcs():
    pcs_query = "SELECT p.*, c.name as category_name FROM pcs p LEFT JOIN categories c ON p.category_id = c.id ORDER BY p.created_at DESC"
    pcs = query_db(pcs_query)
    return render_template('admin/pcs.html', pcs=pcs)

@app.route('/admin/pc/new', methods=['GET', 'POST'])
@login_required
def admin_pc_new():
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'subtitle': request.form.get('subtitle'),
            'description': request.form.get('description'),
            'category_id': request.form.get('category_id'),
            'price': request.form.get('price'),
            'price_old': request.form.get('price_old') or None,
            'processor': request.form.get('processor'),
            'gpu': request.form.get('gpu'),
            'ram': request.form.get('ram'),
            'storage': request.form.get('storage'),
            'motherboard': request.form.get('motherboard'),
            'psu': request.form.get('psu'),
            'case_model': request.form.get('case_model'),
            'cooling': request.form.get('cooling'),
            'graffiti_artist': request.form.get('graffiti_artist'),
            'graffiti_style': request.form.get('graffiti_style'),
            'graffiti_description': request.form.get('graffiti_description'),
            'setup_price': request.form.get('setup_price', 150),
            'featured': 1 if request.form.get('featured') else 0,
            'bestseller': 1 if request.form.get('bestseller') else 0,
            'limited_edition': 1 if request.form.get('limited_edition') else 0,
            'pre_order': 1 if request.form.get('pre_order') else 0,
            'in_stock': 1 if request.form.get('in_stock') else 0,
            'active': 1 if request.form.get('active') else 0
        }
        
        # Gerar slug
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', data['name'].lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        data['slug'] = slug
        
        try:
            insert_query = "INSERT INTO pcs (name, slug, subtitle, description, category_id, price, price_old, processor, gpu, ram, storage, motherboard, psu, case_model, cooling, graffiti_artist, graffiti_style, graffiti_description, setup_price, featured, bestseller, limited_edition, pre_order, in_stock, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            
            execute_db(insert_query, [
                data['name'], data['slug'], data['subtitle'], data['description'], 
                data['category_id'], data['price'], data['price_old'],
                data['processor'], data['gpu'], data['ram'], data['storage'], 
                data['motherboard'], data['psu'], data['case_model'], data['cooling'],
                data['graffiti_artist'], data['graffiti_style'], data['graffiti_description'], data['setup_price'],
                data['featured'], data['bestseller'], data['limited_edition'], data['pre_order'], 
                data['in_stock'], data['active']
            ])
            
            flash('PC criado com sucesso!', 'success')
            return redirect(url_for('admin_pcs'))
            
        except Exception as e:
            flash(f'Erro ao criar PC: {str(e)}', 'error')
    
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    return render_template('admin/pc_form.html', categories=categories, action='new')

@app.route('/admin/pc/edit/<int:pc_id>', methods=['GET', 'POST'])
@login_required
def admin_pc_edit(pc_id):
    pc = query_db('SELECT * FROM pcs WHERE id = ?', [pc_id], one=True)
    if not pc:
        flash('PC não encontrado', 'error')
        return redirect(url_for('admin_pcs'))
    
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'subtitle': request.form.get('subtitle'),
            'description': request.form.get('description'),
            'category_id': request.form.get('category_id'),
            'price': request.form.get('price'),
            'price_old': request.form.get('price_old') or None,
            'processor': request.form.get('processor'),
            'gpu': request.form.get('gpu'),
            'ram': request.form.get('ram'),
            'storage': request.form.get('storage'),
            'motherboard': request.form.get('motherboard'),
            'psu': request.form.get('psu'),
            'case_model': request.form.get('case_model'),
            'cooling': request.form.get('cooling'),
            'graffiti_artist': request.form.get('graffiti_artist'),
            'graffiti_style': request.form.get('graffiti_style'),
            'graffiti_description': request.form.get('graffiti_description'),
            'setup_price': request.form.get('setup_price', 150),
            'featured': 1 if request.form.get('featured') else 0,
            'bestseller': 1 if request.form.get('bestseller') else 0,
            'limited_edition': 1 if request.form.get('limited_edition') else 0,
            'pre_order': 1 if request.form.get('pre_order') else 0,
            'in_stock': 1 if request.form.get('in_stock') else 0,
            'active': 1 if request.form.get('active') else 0
        }
        
        # Gerar slug se necessário
        if not pc['slug'] or data['name'] != pc['name']:
            slug = re.sub(r'[^a-zA-Z0-9\s-]', '', data['name'].lower())
            slug = re.sub(r'[-\s]+', '-', slug)
            data['slug'] = slug
        else:
            data['slug'] = pc['slug']
        
        try:
            update_query = "UPDATE pcs SET name=?, slug=?, subtitle=?, description=?, category_id=?, price=?, price_old=?, processor=?, gpu=?, ram=?, storage=?, motherboard=?, psu=?, case_model=?, cooling=?, graffiti_artist=?, graffiti_style=?, graffiti_description=?, setup_price=?, featured=?, bestseller=?, limited_edition=?, pre_order=?, in_stock=?, active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
            
            execute_db(update_query, [
                data['name'], data['slug'], data['subtitle'], data['description'], 
                data['category_id'], data['price'], data['price_old'],
                data['processor'], data['gpu'], data['ram'], data['storage'], 
                data['motherboard'], data['psu'], data['case_model'], data['cooling'],
                data['graffiti_artist'], data['graffiti_style'], data['graffiti_description'], data['setup_price'],
                data['featured'], data['bestseller'], data['limited_edition'], data['pre_order'], 
                data['in_stock'], data['active'], pc_id
            ])
            
            flash('PC atualizado com sucesso!', 'success')
            return redirect(url_for('admin_pcs'))
            
        except Exception as e:
            flash(f'Erro ao atualizar PC: {str(e)}', 'error')
    
    categories = query_db('SELECT * FROM categories WHERE active = 1 ORDER BY ordem')
    return render_template('admin/pc_form.html', pc=pc, categories=categories, action='edit')

@app.route('/admin/pc/delete/<int:pc_id>', methods=['POST'])
@login_required
def admin_pc_delete(pc_id):
    try:
        execute_db('DELETE FROM pcs WHERE id = ?', [pc_id])
        flash('PC excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir PC: {str(e)}', 'error')
    
    return redirect(url_for('admin_pcs'))

# Admin - Outras seções
@app.route('/admin/games')
@login_required
def admin_games():
    games = query_db('SELECT * FROM games ORDER BY created_at DESC')
    return render_template('admin/games.html', games=games)

@app.route('/admin/orders')
@login_required
def admin_orders():
    orders_query = "SELECT o.*, c.name as customer_name FROM orders o LEFT JOIN customers c ON o.customer_id = c.id ORDER BY o.created_at DESC"
    orders = query_db(orders_query)
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
