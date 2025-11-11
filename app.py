import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import csv, io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif'}

app = Flask(__name__)
app.secret_key = 'change_this_secret_for_demo'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR,'marine_marketplace.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    fullname = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), nullable=False)  # admin, vendor, consumer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    description = db.Column(db.String(400))
    image_path = db.Column(db.String(300))
    vendor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vendor = db.relationship('User', backref='products')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=True)  # keep if product exists
    product_name = db.Column(db.String(200))  # snapshot
    vendor_name = db.Column(db.String(200))   # snapshot seller
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_each = db.Column(db.Float, nullable=False, default=0.0) # snapshot price
    status = db.Column(db.String(30), default='Pending')  # Pending, Processing, Shipped, Delivered, Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    buyer = db.relationship('User', backref='orders')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(role=None):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login first','danger')
                return redirect(url_for('login'))
            if role and session.get('role')!=role and session.get('role')!='admin':
                flash('Access denied','danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        fullname = request.form.get('fullname','').strip()
        role = request.form['role']
        if User.query.filter_by(username=username).first():
            flash('Username exists','danger')
            return redirect(url_for('register'))
        u = User(username=username, password=generate_password_hash(password), fullname=fullname, role=role)
        db.session.add(u); db.session.commit()
        flash('Registered. Please login.','success')
        return redirect(url_for('login'))
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
            if user.role=='vendor':
                return redirect(url_for('vendor_dashboard'))
            elif user.role=='consumer':
                return redirect(url_for('marketplace'))
            else:
                return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('Logged out','info'); return redirect(url_for('index'))

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

@app.route('/vendor/dashboard')
@login_required(role='vendor')
def vendor_dashboard():
    user = User.query.get(session['user_id'])
    products = Product.query.filter_by(vendor_id=user.id).all()
    # recent orders for this vendor
    orders = Order.query.filter_by(vendor_name=user.fullname or user.username).order_by(Order.created_at.desc()).all()
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
            if not allowed_file(f.filename):
                flash('Invalid image','danger'); return redirect(url_for('add_product'))
            fn = secure_filename(f"{session['username']}_{int(datetime.utcnow().timestamp())}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            imgpath = f"uploads/{fn}"
        p = Product(name=name, price=price, quantity=qty, description=desc, image_path=imgpath, vendor_id=session['user_id'])
        db.session.add(p); db.session.commit()
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
        db.session.commit(); flash('Updated','success'); return redirect(url_for('add_product'))
    return render_template('edit_product.html', product=p)

@app.route('/delete_product/<int:pid>')
@login_required(role='vendor')
def delete_product(pid):
    p = Product.query.get_or_404(pid)
    if p.vendor_id!=session['user_id'] and session.get('role')!='admin':
        flash('Access denied','danger'); return redirect(url_for('marketplace'))
    # Do not delete order snapshots; just remove product record
    db.session.delete(p); db.session.commit()
    flash('Product removed','info'); return redirect(request.referrer or url_for('vendor_dashboard'))

@app.route('/marketplace')
def marketplace():
    q = request.args.get('q','').strip()
    minp = request.args.get('min','').strip()
    maxp = request.args.get('max','').strip()
    products = Product.query
    if q: products = products.filter(Product.name.ilike(f'%{q}%'))
    try:
        if minp: products = products.filter(Product.price >= float(minp))
        if maxp: products = products.filter(Product.price <= float(maxp))
    except: pass
    products = products.order_by(Product.created_at.desc()).all()
    return render_template('marketplace.html', products=products, q=q, minp=minp, maxp=maxp)

@app.route('/product/<int:pid>')
def product_detail(pid):
    p = Product.query.get_or_404(pid)
    return render_template('product_detail.html', p=p)

@app.route('/order/<int:pid>', methods=['GET','POST'])
@login_required(role='consumer')
def order(pid):
    p = Product.query.get_or_404(pid)
    if request.method=='POST':
        qty = int(request.form['quantity'])
        if qty<=0 or qty>p.quantity:
            flash('Invalid qty','danger'); return redirect(url_for('order', pid=pid))
        # snapshot product info into order so deletion won't show 'Deleted'
        vendor = p.vendor.fullname or p.vendor.username if p.vendor else ''
        o = Order(product_id=p.id, product_name=p.name, vendor_name=vendor, buyer_id=session['user_id'], quantity=qty, price_each=p.price)
        p.quantity -= qty
        db.session.add(o); db.session.commit(); flash('Order placed','success'); return redirect(url_for('orders'))
    return render_template('order.html', product=p)

@app.route('/orders')
@login_required()
def orders():
    role = session.get('role')
    if role=='consumer':
        orders = Order.query.filter_by(buyer_id=session['user_id']).order_by(Order.created_at.desc()).all()
    elif role=='vendor':
        user = User.query.get(session['user_id']); orders = Order.query.filter_by(vendor_name=user.fullname or user.username).order_by(Order.created_at.desc()).all()
    elif role=='admin':
        orders = Order.query.order_by(Order.created_at.desc()).all()
    else:
        orders = []
    return render_template('orders.html', orders=orders)

@app.route('/update_order/<int:oid>', methods=['POST'])
@login_required()
def update_order(oid):
    o = Order.query.get_or_404(oid)
    new = request.form.get('status')
    # only admin or vendor of that order can update
    if session.get('role')!='admin':
        vendor = User.query.filter((User.fullname==o.vendor_name) | (User.username==o.vendor_name)).first()
        if not vendor or vendor.id!=session.get('user_id'):
            flash('Access denied','danger'); return redirect(url_for('orders'))
    if new in ('Pending','Processing','Shipped','Delivered','Cancelled'):
        o.status = new; db.session.commit(); flash('Order updated','success')
    return redirect(request.referrer or url_for('orders'))

@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    total_users = User.query.count(); total_products = Product.query.count(); total_orders = Order.query.count()
    return render_template('admin_dashboard.html', total_users=total_users, total_products=total_products, total_orders=total_orders)

@app.route('/reports')
@login_required()
def reports():
    # only admin or vendor
    if session.get('role') not in ('admin','vendor'): flash('Access denied','danger'); return redirect(url_for('index'))
    return render_template('reports.html')

@app.route('/reports/data')
@login_required()
def reports_data():
    role = session.get('role'); now = datetime.utcnow()
    labels=[]; values=[]
    for i in range(6,-1,-1):
        dt = now - timedelta(days=i)
        start = datetime(dt.year, dt.month, dt.day)
        end = start + timedelta(days=1)
        q = db.session.query(db.func.sum(Order.price_each*Order.quantity)).filter(Order.created_at>=start, Order.created_at<end, Order.status=='Delivered')
        if role=='vendor':
            user = User.query.get(session['user_id'])
            q = q.filter(Order.vendor_name== (user.fullname or user.username))
        total = q.scalar() or 0
        labels.append(start.strftime('%Y-%m-%d')); values.append(float(total))
    # top products
    if role=='admin':
        top = db.session.query(Order.product_name, db.func.sum(Order.quantity).label('qty')).group_by(Order.product_name).order_by(db.desc('qty')).limit(5).all()
    else:
        user = User.query.get(session['user_id'])
        top = db.session.query(Order.product_name, db.func.sum(Order.quantity).label('qty')).filter(Order.vendor_name==(user.fullname or user.username)).group_by(Order.product_name).order_by(db.desc('qty')).limit(5).all()
    top_list = [{'name': t[0], 'qty': int(t[1])} for t in top]
    total_revenue_q = db.session.query(db.func.sum(Order.price_each*Order.quantity)).filter(Order.status=='Delivered')
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
        cw.writerow([o.id, o.product_name, o.vendor_name, buyer, o.quantity, o.status, o.price_each, o.price_each*o.quantity, o.created_at.strftime('%Y-%m-%d %H:%M')])
    output = make_response(si.getvalue()); output.headers["Content-Disposition"] = "attachment; filename=sales.csv"; output.headers["Content-type"]="text/csv"
    return output

if __name__=='__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
