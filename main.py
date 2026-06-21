import os
from flask import Flask, render_template, request, redirect, session, jsonify, url_for

app = Flask(__name__)

# --- COPY & PASTE THIS DATABASE FIX CONFIGURATION ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'mango_store.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# ----------------------------------------------------

db = SQLAlchemy(app)
# ==========================================
# CHANGE YOUR CONFIGURATION CREDENTIALS HERE
# ==========================================
ADMIN_USERNAME = "Radha-krishn"  # <--- Change your username here
ADMIN_PASSWORD = "radha@opl12"  # <--- Change your password here

# DATABASE MODELS
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    desc = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(255), nullable=True)


class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Integer, nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player = db.Column(db.String(100), nullable=False)
    purchased_items = db.Column(db.Text, nullable=False)
    total = db.Column(db.String(100), nullable=False)
    discount_applied = db.Column(db.String(100), default="None")
    status = db.Column(db.String(50), default="Pending")
    rejection_reason = db.Column(db.Text, nullable=True)


def seed_default_data():
    if Product.query.count() == 0:
        db.session.add(Product(category="rank", name="VIP Rank Upgrade", price=250,
                               desc="Get the [VIP] prefix and /fly in lobbies.", img_url=""))
        db.session.add(Product(category="rank", name="MVP Elite Rank", price=600,
                               desc="Get the [MVP] bold prefix and /feed access.", img_url=""))
        db.session.add(
            Product(category="crates", name="Mythic Crate Key", price=80, desc="Open spawn crates for legendary drops.",
                    img_url=""))
        db.session.commit()
    if Coupon.query.count() == 0:
        db.session.add(Coupon(code="MANGO20", type="Percentage", value=20))
        db.session.commit()


with app.app_context():
    db.create_all()
    with db.engine.connect() as conn:
        try:
            conn.execute(db.text("ALTER TABLE `order` ADD COLUMN discount_applied VARCHAR(100) DEFAULT 'None'"))
        except Exception:
            pass
        try:
            conn.execute(db.text("ALTER TABLE `order` ADD COLUMN rejection_reason TEXT"))
        except Exception:
            pass
    seed_default_data()


# PUBLIC FRONTEND ROUTES
@app.route('/')
def home():
    category = request.args.get('category', 'rank')
    products = Product.query.filter_by(category=category).all()
    all_prods = {cat: Product.query.filter_by(category=cat).all() for cat in
                 ['rank', 'crates', 'cash', 'power', 'spacial']}
    return render_template('store.html', products=all_prods, selected_cat=category, items=products, admin_view=False)


@app.route('/validate_coupon', methods=['POST'])
def validate_coupon():
    data = request.get_json()
    code_entered = data.get('code', '').upper().strip()
    coupon = Coupon.query.filter_by(code=code_entered).first()
    if coupon: return jsonify({"success": True, "type": coupon.type, "value": coupon.value})
    return jsonify({"success": False, "message": "Invalid Coupon Code"})


@app.route('/payment', methods=['POST'])
def payment_gateway():
    username = request.form.get('mc_username')
    product_ids = request.form.getlist('product_ids[]')
    quantities = request.form.getlist('quantities[]')
    applied_coupon = request.form.get('applied_coupon_code', '')

    order_items = []
    subtotal = 0
    for p_id, qty in zip(product_ids, quantities):
        product = Product.query.get(int(p_id))
        if product and int(qty) > 0:
            subtotal += product.price * int(qty)
            order_items.append({"id": p_id, "name": product.name, "qty": int(qty), "cost": product.price * int(qty)})

    if not order_items: return redirect(url_for('home'))

    final_cost = subtotal
    discount_string = "None"
    if applied_coupon:
        cp = Coupon.query.filter_by(code=applied_coupon.upper().strip()).first()
        if cp:
            if cp.type == "Percentage":
                final_cost = max(0, subtotal - (subtotal * (cp.value / 100)))
                discount_string = f"{cp.code} (-₹{int(subtotal * (cp.value / 100))})"
            else:
                final_cost = max(0, subtotal - cp.value)
                discount_string = f"{cp.code} (-₹{cp.value})"

    return render_template('store.html', show_payment_screen=True, player=username, total_cost=int(final_cost),
                           items_json=json.dumps(order_items), discount_str=discount_string)


@app.route('/checkout', methods=['POST'])
def checkout():
    username = request.form.get('mc_username')
    items_json = request.form.get('items_json')
    payment_method = request.form.get('payment_method', 'Unknown')
    total_paid = request.form.get('total_paid')
    discount_str = request.form.get('discount_str', 'None')

    new_order = Order(player=username, purchased_items=items_json, total=f"₹{total_paid} (Paid via {payment_method})",
                      discount_applied=discount_str, status="Pending")
    db.session.add(new_order)
    db.session.commit()
    return render_template('store.html', reveal=True, player=username,
                           chosen_rank=", ".join([f"{i['qty']}x {i['name']}" for i in json.loads(items_json)]))


# ==========================================
# ADMIN ROUTING & SECURE LOGIN GATEWAY
# ==========================================
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        user = request.form.get('username')
        password = request.form.get('password')

        # Checking if details match our variables
        if user == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('store.html', admin_view=True, login_failed=True, show_login_screen=True)

    # If not logged in, show the username and password page
    if not session.get('admin_logged_in'):
        return render_template('store.html', admin_view=True, show_login_screen=True)

    current_tab = request.args.get('tab', 'orders')
    all_products = Product.query.all()
    all_orders = Order.query.all()
    all_coupons = Coupon.query.all()

    active_orders = []
    history_orders = []
    for o in all_orders:
        data = {"id": o.id, "player": o.player, "total": o.total, "status": o.status, "discount": o.discount_applied,
                "reason": o.rejection_reason, "items": json.loads(o.purchased_items)}
        if o.status == 'Pending':
            active_orders.append(data)
        else:
            history_orders.append(data)

    return render_template('store.html', admin_view=True, active_tab=current_tab, products=all_products,
                           orders=active_orders, history_orders=history_orders, coupons=all_coupons)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))


@app.route('/admin/order/<int:order_id>/<action>', methods=['POST'])
def handle_order(order_id, action):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_panel'))
    order = Order.query.get_or_404(order_id)
    if action == 'accept':
        order.status = 'Success'
    elif action == 'decline':
        order.status = 'Declined'
        order.rejection_reason = request.form.get('reason', 'No reason provided.')
    db.session.commit()
    return redirect(url_for('admin_panel', tab='orders'))


@app.route('/admin/save_product', methods=['POST'])
def save_product():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_panel'))
    p_id = request.form.get('product_id')
    cat = request.form.get('category')
    name = request.form.get('name')
    price_val = int(request.form.get('price', 0))
    desc = request.form.get('description')

    file = request.files.get('image_file')
    filename = ""
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        filename = f"/static/uploads/{filename}"

    if p_id:
        product = Product.query.get(int(p_id))
        if product:
            product.category = cat;
            product.name = name;
            product.price = price_val;
            product.desc = desc
            if filename: product.img_url = filename
    else:
        db.session.add(Product(category=cat, name=name, price=price_val, desc=desc, img_url=filename))

    db.session.commit()
    return redirect(url_for('admin_panel', tab='product'))


@app.route('/admin/delete_product/<int:id>')
def delete_product(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_panel'))
    prod = Product.query.get(id)
    if prod: db.session.delete(prod); db.session.commit()
    return redirect(url_for('admin_panel', tab='product'))


@app.route('/admin/save_coupon', methods=['POST'])
def save_coupon():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_panel'))
    code = request.form.get('code').upper().strip()
    db.session.add(Coupon(code=code, type=request.form.get('type'), value=int(request.form.get('value', 0))))
    db.session.commit()
    return redirect(url_for('admin_panel', tab='coupons'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
