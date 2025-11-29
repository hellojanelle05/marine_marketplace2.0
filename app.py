import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, make_response, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import csv, io

# ---------- Config ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.secret_key = os.environ.get('APP_SECRET', 'bahoNitope')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR,'marine_marketplace.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

db = SQLAlchemy(app)

# ---------- MODELS ----------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    fullname = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), nullable=False)  # admin, vendor, consumer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username}>"

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.String(400))
    image_path = db.Column(db.String(300))
    vendor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vendor = db.relationship('User', backref='products')

    def __repr__(self):
        return f"<Product {self.name}>"

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)

    # snapshot fields (single-product order model)
    product_id = db.Column(db.Integer, nullable=True)  # snapshot of product id
    product_name = db.Column(db.String(200))
    vendor_name = db.Column(db.String(200))

    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_each = db.Column(db.Float, nullable=False, default=0.0)

    status = db.Column(db.String(30), default='Pending')  # Pending, Processing, Shipped, Delivered, Cancelled, Paid
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    buyer = db.relationship('User', backref='orders')

    # Relationship to order_items (kept for compatibility but single item expected)
    order_items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

    payments = db.relationship('Payment', backref='order', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Order {self.id} product={self.product_name} buyer={self.buyer_id}>"

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_each = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')

    def __repr__(self):
        return f"<OrderItem {self.id} order={self.order_id} product={self.product_id}>"

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    payment_status = db.Column(db.String(50), default='Pending')  # Pending / Completed / Failed
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Payment {self.id} order={self.order_id} amount={self.amount_paid}>"

class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    address_line = db.Column(db.String(250), nullable=False)
    barangay = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    province = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='addresses')

class ProductReview(db.Model):
    __tablename__ = 'product_reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    rating = db.Column(db.Integer)
    review = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')
    product = db.relationship('Product')

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(200))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    actor = db.relationship('User')

# ---------- Helpers ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login first','warning')
                return redirect(url_for('login'))
            if role and session.get('role') != role and session.get('role') != 'admin':
                flash('Access denied','danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

def log_action(actor_id, action, description=''):
    try:
        a = AuditLog(actor_id=actor_id, action=action, description=description)
        db.session.add(a)
        db.session.commit()
    except Exception:
        db.session.rollback()

# ---------- ROUTES ----------
@app.route('/')
def index():
    return redirect(url_for('marketplace'))

@app.route('/about')
def about():
    return render_template('about.html')

# ---------- AUTH ----------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        fullname = request.form.get('fullname','').strip()
        role = request.form.get('role','consumer')
        if User.query.filter_by(username=username).first():
            flash('Username exists','danger'); return redirect(url_for('register'))
        u = User(username=username, password=generate_password_hash(password), fullname=fullname, role=role)
        db.session.add(u); db.session.commit()
        flash('Registered. Please login.','success'); return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id']=user.id
            session['username']=user.username
            session['fullname']=user.fullname or user.username
            session['role']=user.role
            flash(f'Welcome {session["fullname"]}!','success')
            log_action(user.id, 'login', 'User logged in')
            # redirect by role
            if user.role=='vendor': return redirect(url_for('vendor_dashboard'))
            if user.role=='consumer': return redirect(url_for('marketplace'))
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    uid = session.get('user_id')
    session.clear(); flash('Logged out','info')
    log_action(uid, 'logout', 'User logged out')
    return redirect(url_for('index'))

@app.route('/create_admin', methods=['GET','POST'])
def create_admin():
    if User.query.filter_by(role='admin').first():
        flash('Admin exists','warning'); return redirect(url_for('login'))
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        fullname = request.form.get('fullname','Administrator')
        u = User(username=username, password=generate_password_hash(password), fullname=fullname, role='admin')
        db.session.add(u); db.session.commit()
        flash('Admin created','success'); return redirect(url_for('login'))
    return render_template('create_admin.html')

# ---------- VENDOR ----------
@app.route('/vendor/dashboard')
@login_required(role='vendor')
def vendor_dashboard():
    user = User.query.get(session['user_id'])
    products = Product.query.filter_by(vendor_id=user.id).all()
    # orders where vendor_name matches vendor fullname or username
    vname = user.fullname or user.username
    orders = Order.query.filter_by(vendor_name=vname).order_by(Order.created_at.desc()).all()
    return render_template('vendor_dashboard.html', user=user, products=products, orders=orders)

@app.route('/add_product', methods=['GET','POST'])
@login_required(role='vendor')
def add_product():
    if request.method=='POST':
        name = request.form['name'].strip()
        price = float(request.form['price'])
        qty = int(request.form['quantity'])
        desc = request.form.get('description','').strip()
        f = request.files.get('image')
        imgpath = None
        if f and f.filename:
            if not allowed_file(f.filename): flash('Invalid image','danger'); return redirect(url_for('add_product'))
            fn = secure_filename(f"{session['username']}_{int(datetime.utcnow().timestamp())}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            imgpath = f"uploads/{fn}"
        p = Product(name=name, price=price, quantity=qty, description=desc, image_path=imgpath, vendor_id=session['user_id'])
        db.session.add(p); db.session.commit()
        log_action(session['user_id'], 'add_product', f'Added product {name}')
        flash('Product added','success'); return redirect(url_for('add_product'))
    my_products = Product.query.filter_by(vendor_id=session['user_id']).all()
    return render_template('add_product.html', products=my_products)

@app.route('/edit_product/<int:pid>', methods=['GET','POST'])
@login_required(role='vendor')
def edit_product(pid):
    p = Product.query.get_or_404(pid)
    if p.vendor_id!=session['user_id'] and session.get('role')!='admin':
        flash('Access denied','danger'); return redirect(url_for('marketplace'))
    if request.method=='POST':
        p.name = request.form['name'].strip()
        p.price = float(request.form['price']); p.quantity = int(request.form['quantity']); p.description = request.form.get('description','').strip()
        f = request.files.get('image')
        if f and f.filename and allowed_file(f.filename):
            fn = secure_filename(f"{session['username']}_{int(datetime.utcnow().timestamp())}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            p.image_path = f"uploads/{fn}"
        db.session.commit(); log_action(session['user_id'], 'edit_product', f'Edited product {p.id}')
        flash('Updated','success'); return redirect(url_for('add_product'))
    return render_template('edit_product.html', product=p)

@app.route('/delete_product/<int:pid>')
@login_required(role='vendor')
def delete_product(pid):
    p = Product.query.get_or_404(pid)
    if p.vendor_id!=session['user_id'] and session.get('role')!='admin':
        flash('Access denied','danger'); return redirect(url_for('marketplace'))
    db.session.delete(p); db.session.commit()
    log_action(session['user_id'], 'delete_product', f'Deleted product {pid}')
    flash('Product removed','info'); return redirect(request.referrer or url_for('vendor_dashboard'))

# ---------- MARKETPLACE ----------
@app.route('/marketplace')
def marketplace():
    q = request.args.get('q','').strip()
    minp = request.args.get('min','').strip()
    maxp = request.args.get('max','').strip()
    products_q = Product.query
    if q: products_q = products_q.filter(Product.name.ilike(f'%{q}%'))
    try:
        if minp: products_q = products_q.filter(Product.price >= float(minp))
        if maxp: products_q = products_q.filter(Product.price <= float(maxp))
    except:
        pass
    products = products_q.order_by(Product.created_at.desc()).all()
    return render_template('marketplace.html', products=products, q=q, minp=minp, maxp=maxp)

@app.route('/product/<int:pid>')
def product_detail(pid):
    p = Product.query.get_or_404(pid)
    reviews = ProductReview.query.filter_by(product_id=pid).order_by(ProductReview.created_at.desc()).all()
    return render_template('product_detail.html', p=p, reviews=reviews)

# ---------- ORDER + PAYMENT ----------
@app.route('/order/<int:pid>', methods=['GET','POST'])
@login_required(role='consumer')
def order(pid):
    p = Product.query.get_or_404(pid)
    if request.method=='POST':
        qty = int(request.form['quantity'])
        if qty<=0 or qty>p.quantity:
            flash('Invalid qty','danger'); return redirect(url_for('order', pid=pid))
        vendor = p.vendor.fullname or p.vendor.username if p.vendor else ''
        # create snapshot Order
        o = Order(product_id=p.id, product_name=p.name, vendor_name=vendor,
                  buyer_id=session['user_id'], quantity=qty, price_each=p.price, status='Pending')
        db.session.add(o)
        db.session.flush()  # get o.id
        # create OrderItem for record (keeps details consistent)
        oi = OrderItem(order_id=o.id, product_id=p.id, quantity=qty, price_each=p.price, subtotal=round(qty * p.price,2))
        p.quantity -= qty
        db.session.add(oi)
        db.session.commit()
        log_action(session['user_id'], 'create_order', f'Order {o.id} for product {p.id}')
        flash('Order placed. Please proceed to payment.','success')
        return redirect(url_for('pay', oid=o.id))
    return render_template('order.html', product=p)

@app.route('/pay/<int:oid>', methods=['GET','POST'])
@login_required(role='consumer')
def pay(oid):
    o = Order.query.get_or_404(oid)
    if o.buyer_id != session.get('user_id'):
        flash('Access denied','danger'); return redirect(url_for('orders'))
    # calc total
    if o.order_items:
        total = sum([it.subtotal for it in o.order_items])
    else:
        total = o.price_each * o.quantity
    if request.method=='POST':
        method = request.form.get('method','COD')
        status = 'Completed' if method != 'Cash on Delivery' and method != 'COD' else 'Pending'
        pay = Payment(order_id=o.id, amount_paid=total, payment_method=method, payment_status=status)
        db.session.add(pay)
        if status == 'Completed':
            o.status = 'Paid'
        db.session.commit()
        log_action(session.get('user_id'), 'payment', f'Payment {pay.id} method={method} order={o.id}')
        flash('Payment recorded','success')
        return redirect(url_for('payment_success', oid=o.id))
    return render_template('payment.html', order=o, total=total)

@app.route('/process_payment/<int:order_id>', methods=['POST'])
@login_required
def process_payment(order_id):
    payment_method = request.form.get('payment_method')

    conn = get_db_connection()

    # Verify order exists and belongs to the user
    order = conn.execute(
        "SELECT * FROM orders WHERE id = ? AND customer_id = ?",
        (order_id, session['user_id'])
    ).fetchone()

    if not order:
        conn.close()
        flash("Order not found.", "danger")
        return redirect(url_for('orders'))

    # Update payment record
    conn.execute(
        "UPDATE orders SET payment_method = ?, payment_status = 'Paid' WHERE id = ?",
        (payment_method, order_id)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('payment_success'))


@app.route('/payment_success/<int:oid>')
@login_required(role='consumer')
def payment_success(oid):
    o = Order.query.get_or_404(oid)
    latest_payment = Payment.query.filter_by(order_id=o.id).order_by(Payment.payment_date.desc()).first()
    return render_template('payment_success.html', order=o, payment=latest_payment)

@app.route('/order_details/<int:oid>')
@login_required()
def order_details(oid):
    o = Order.query.get_or_404(oid)
    # permission: buyer, vendor (match vendor_name), or admin
    if session.get('role') == 'consumer' and o.buyer_id != session.get('user_id'):
        flash('Access denied','danger'); return redirect(url_for('orders'))
    if session.get('role') == 'vendor':
        user = User.query.get(session['user_id'])
        if o.vendor_name != (user.fullname or user.username):
            flash('Access denied','danger'); return redirect(url_for('orders'))
    return render_template('order_details.html', order=o)

@app.route('/orders')
@login_required()
def orders():
    role = session.get('role')
    if role=='consumer':
        orders_q = Order.query.filter_by(buyer_id=session['user_id']).order_by(Order.created_at.desc())
    elif role=='vendor':
        user = User.query.get(session['user_id'])
        vname = user.fullname or user.username
        orders_q = Order.query.filter_by(vendor_name=vname).order_by(Order.created_at.desc())
    elif role=='admin':
        orders_q = Order.query.order_by(Order.created_at.desc())
    else:
        orders_q = Order.query.filter(False)
    orders = orders_q.all()
    return render_template('orders.html', orders=orders)

@app.route('/update_order/<int:oid>', methods=['POST'])
@login_required()
def update_order(oid):
    o = Order.query.get_or_404(oid)
    new = request.form.get('status')
    # only admin or vendor-of-order can update
    if session.get('role')!='admin':
        user = User.query.get(session['user_id'])
        if o.vendor_name != (user.fullname or user.username):
            flash('Access denied','danger'); return redirect(url_for('orders'))
    if new in ('Pending','Processing','Shipped','Delivered','Cancelled','Paid'):
        o.status = new; db.session.commit(); log_action(session.get('user_id'), 'update_order', f'Order {oid} set {new}')
        flash('Order updated','success')
    return redirect(request.referrer or url_for('orders'))

# ---------- PAYMENTS (views for roles) ----------
@app.route('/my_payments')
@login_required(role='consumer')
def my_payments():
    uid = session.get('user_id')
    payments = Payment.query.join(Order, Payment.order_id == Order.id).filter(Order.buyer_id == uid).order_by(Payment.payment_date.desc()).all()
    return render_template('payments/my_payments.html', payments=payments)

@app.route('/vendor_payments')
@login_required(role='vendor')
def vendor_payments():
    user = User.query.get(session['user_id'])
    vname = user.fullname or user.username
    payments = Payment.query.join(Order, Payment.order_id == Order.id).filter(Order.vendor_name == vname).order_by(Payment.payment_date.desc()).all()
    return render_template('payments/vendor_payments.html', payments=payments)

@app.route('/admin_payments')
@login_required(role='admin')
def admin_payments():
    payments = Payment.query.order_by(Payment.payment_date.desc()).all()
    return render_template('payments/admin_payments.html', payments=payments)

@app.route('/transactions')
@login_required(role='consumer')
def transactions():
    uid = session.get('user_id')
    txs = Payment.query.join(Order, Payment.order_id == Order.id).filter(Order.buyer_id == uid).order_by(Payment.payment_date.desc()).all()
    return render_template('transaction_history.html', transactions=txs)

# ---------- Address manager ----------
@app.route('/addresses', methods=['GET','POST'])
@login_required(role='consumer')
def address_manager():
    uid = session.get('user_id')
    if request.method=='POST':
        address_line = request.form.get('address_line','').strip()
        barangay = request.form.get('barangay','').strip()
        city = request.form.get('city','').strip()
        province = request.form.get('province','').strip()
        phone = request.form.get('phone','').strip()
        if not address_line or not barangay or not city or not province or not phone:
            flash('Please fill all address fields','danger'); return redirect(url_for('address_manager'))
        a = Address(user_id=uid, address_line=address_line, barangay=barangay, city=city, province=province, phone=phone)
        db.session.add(a); db.session.commit()
        log_action(uid, 'add_address', f'Added address {a.id}')
        flash('Address added','success'); return redirect(url_for('address_manager'))
    addresses = Address.query.filter_by(user_id=uid).order_by(Address.created_at.desc()).all()
    return render_template('address_manager.html', addresses=addresses)

@app.route('/address_delete/<int:aid>', methods=['POST'])
@login_required(role='consumer')
def address_delete(aid):
    a = Address.query.get_or_404(aid)
    if a.user_id != session.get('user_id'):
        flash('Access denied','danger'); return redirect(url_for('address_manager'))
    db.session.delete(a); db.session.commit()
    log_action(session.get('user_id'), 'delete_address', f'Deleted address {aid}')
    flash('Address deleted','success'); return redirect(url_for('address_manager'))

# ---------- Reviews ----------
@app.route('/reviews/<int:pid>', methods=['GET','POST'])
def reviews(pid):
    product = Product.query.get_or_404(pid)
    if request.method=='POST':
        if 'user_id' not in session:
            flash('Please login to add a review','warning'); return redirect(url_for('login'))
        rating = int(request.form.get('rating',5))
        review_text = request.form.get('review','').strip()
        r = ProductReview(user_id=session['user_id'], product_id=pid, rating=rating, review=review_text)
        db.session.add(r); db.session.commit()
        log_action(session['user_id'], 'add_review', f'Review for product {pid}')
        flash('Review posted','success'); return redirect(url_for('reviews', pid=pid))
    revs = ProductReview.query.filter_by(product_id=pid).order_by(ProductReview.created_at.desc()).all()
    return render_template('reviews.html', product=product, reviews=revs)

# ---------- Audit logs (admin) ----------
@app.route('/audit_logs')
@login_required(role='admin')
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
    return render_template('audit_logs.html', logs=logs)

# ---------- ADMIN DASHBOARD & REPORTS ----------
@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    total_users = User.query.count(); total_products = Product.query.count(); total_orders = Order.query.count()
    return render_template('admin_dashboard.html', total_users=total_users, total_products=total_products, total_orders=total_orders)

@app.route('/reports')
@login_required()
def reports():
    if session.get('role') not in ('admin','vendor'):
        flash('Access denied','danger'); return redirect(url_for('index'))
    return render_template('reports.html')

@app.route('/reports/data')
@login_required()
def reports_data():
    role = session.get('role'); now = datetime.utcnow()
    labels=[]; values=[]
    from sqlalchemy import func, desc
    # daily revenue for last 7 days (based on orders and price_each*quantity, delivered)
    for i in range(6,-1,-1):
        dt = now - timedelta(days=i)
        start = datetime(dt.year, dt.month, dt.day)
        end = start + timedelta(days=1)
        q = db.session.query(func.sum(Order.price_each*Order.quantity)).filter(Order.created_at>=start, Order.created_at<end, Order.status=='Delivered')
        if role=='vendor':
            user = User.query.get(session['user_id'])
            q = q.filter(Order.vendor_name== (user.fullname or user.username))
        total = q.scalar() or 0
        labels.append(start.strftime('%Y-%m-%d')); values.append(float(total))
    # top products
    if role=='admin':
        top = db.session.query(Order.product_name, func.sum(Order.quantity).label('qty')).group_by(Order.product_name).order_by(desc('qty')).limit(5).all()
    else:
        user = User.query.get(session['user_id'])
        top = db.session.query(Order.product_name, func.sum(Order.quantity).label('qty')).filter(Order.vendor_name==(user.fullname or user.username)).group_by(Order.product_name).order_by(desc('qty')).limit(5).all()
    top_list = [{'name': t[0], 'qty': int(t[1])} for t in top]
    total_revenue_q = db.session.query(func.sum(Order.price_each*Order.quantity)).filter(Order.status=='Delivered')
    if role=='vendor':
        user = User.query.get(session['user_id']); total_revenue_q = total_revenue_q.filter(Order.vendor_name==(user.fullname or user.username))
    total_revenue = float(total_revenue_q.scalar() or 0)
    total_orders = Order.query.count() if role=='admin' else Order.query.filter(Order.vendor_name==(User.query.get(session['user_id']).fullname or User.query.get(session['user_id']).username)).count()
    return jsonify({'labels':labels,'values':values,'top_products':top_list,'total_revenue':total_revenue,'total_orders':total_orders})

@app.route('/reports/export_csv')
@login_required()
def export_csv():
    si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(['Order ID','Product','Vendor','Buyer','Qty','Status','Price Each','Total','Date'])
    q = Order.query.order_by(Order.created_at.desc())
    for o in q.all():
        buyer = User.query.get(o.buyer_id).username if o.buyer_id else ''
        cw.writerow([o.id, o.product_name, o.vendor_name, buyer, o.quantity, o.status, o.price_each, round(o.price_each*o.quantity,2), o.created_at.strftime('%Y-%m-%d %H:%M')])
    output = make_response(si.getvalue()); output.headers["Content-Disposition"] = "attachment; filename=sales.csv"; output.headers["Content-type"]="text/csv"
    return output

# ---------- Utility / debug routes ----------
@app.route('/whoami')
def whoami():
    if 'user_id' in session:
        return jsonify({'user_id': session['user_id'], 'username': session.get('username'), 'role': session.get('role')})
    return jsonify({'user': None})

# ---------- START ----------
if __name__=='__main__':
    # ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
