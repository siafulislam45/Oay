import os
import random
import string
import requests
import base64
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, make_response
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import timedelta
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "TypeYourRandomSecretKeyHere123")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7) # ৭ দিন লগিন থাকবে
# -------------------------------------------------------------------
# 1. DATABASE CONNECTION (Supabase)
# -------------------------------------------------------------------
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Supabase URL and Key must be set in .env or Vercel Environment Variables")

supabase: Client = create_client(url, key)


# --- SPECIAL TASK CONFIG ---
SPECIAL_TASK_INFO = {
    'title': '🔥 Airdrop Transfer & Registration',
    'reward': 50.00,
    'link': 'https://t.me/TelasterBot?start=23212', 
    'tutorial': 'https://payr.site/st', 
    'description': 'ভিডিও দেখে নিয়ম মেনে Bot  Start করে, রেপারাল লিংক কপি করুন এবং এয়ারড্রপ ট্রান্সফার করুন এবং প্রুফ জমা দিন।'
}

# --- VIP LEVEL CONFIGURATION ---
VIP_PLANS = {
    1: {'name': 'Starter', 'price': 100, 'daily_profit': 10, 'days': 14, 'min_withdraw': 200},
    2: {'name': 'Basic', 'price': 200, 'daily_profit': 20, 'days': 17, 'min_withdraw': 200},
    3: {'name': 'Standard', 'price': 500, 'daily_profit': 30, 'days': 45, 'min_withdraw': 200},
    4: {'name': 'Pro', 'price': 1000, 'daily_profit': 60, 'days': 60, 'min_withdraw': 200},
    5: {'name': 'Elite', 'price': 5000, 'daily_profit': 350, 'days': 90, 'min_withdraw': 200}
}

# --- MIDDLEWARE (UPDATED FOR BAN SYSTEM) ---
@app.before_request
def before_request_checks():

    # 🚀 [NEW] URL REDIRECT LOGIC (Instant Transfer)
    # যদি কেউ পুরনো লিংকে আসে, তাকে নতুন লিংকে পাঠিয়ে দিবে
    if request.host == 'taskking.vercel.app':
        return redirect('https://kaikor.vercel.app/', code=301)
        
    # ১. সেটিংস লোড
    try:
        response = supabase.table('site_settings').select('*').eq('id', 1).single().execute()
        g.settings = response.data
    except:
        g.settings = {'maintenance_mode': False, 'activation_required': False, 'notice_text': ''}

    # ২. ইউজার লোড
    g.user = None
    if 'user_id' in session:
        try:
            user_resp = supabase.table('profiles').select('*').eq('id', session['user_id']).single().execute()
            g.user = user_resp.data
            
            # --- [NEW] BAN CHECK LOGIC ---
            if g.user.get('is_banned'):
                # এই পেজগুলো ব্যান থাকলেও এক্সেস করা যাবে (Logout & Static files)
                allowed_while_banned = ['static', 'logout']
                
                if request.endpoint not in allowed_while_banned:
                    # অন্য সব পেজের বদলে ব্যান পেজ দেখাবে
                    return render_template('banned.html', user=g.user)

            # Last Active Update
            if request.endpoint in ['dashboard', 'tasks', 'account', 'history']:
                try:
                    from datetime import datetime
                    supabase.table('profiles').update({'last_login': datetime.now().isoformat()}).eq('id', session['user_id']).execute()
                except: pass

        except Exception as e:
            print(f"User Fetch Error: {e}")

    # ৩. মেইনটেনেন্স মোড
    if g.settings.get('maintenance_mode'):
        allowed_public = ['static', 'login', 'logout', 'admin_login']
        if request.endpoint in allowed_public:
            return
        if g.user and g.user.get('role') == 'admin':
            return
        return render_template('maintenance.html')

    # ৪. এক্টিভেশন চেক
    if g.settings.get('activation_required'):
        if g.user and not g.user.get('is_active') and g.user.get('role') != 'admin':
            restricted_pages = ['tasks', 'submit_task', 'withdraw']
            if request.endpoint in restricted_pages:
                flash("⚠️ এই সুবিধা পেতে একাউন্ট ভেরিফাই করুন!", "error")
                return redirect(url_for('activate_account'))
# -------------------------------------------------------------------
# 3. HELPER DECORATORS
# -------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- HELPER: UNIQUE CODE GENERATOR ---
def generate_ref_code():
    # TK + 4 Random Digits/Letters (Example: TK4A2B)
    chars = string.ascii_uppercase + string.digits
    code = 'PR' + ''.join(random.choices(chars, k=4))
    return code
    
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user or g.user.get('role') != 'admin':
            flash("⚠️ শুধুমাত্র এডমিন প্রবেশ করতে পারবে।", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function
    
# --- HELPER: SUB-ADMIN DECORATOR (UPDATED) ---
def sub_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # স্পেসিফিক ইমেইল (মাসুমা আপু)
        sub_admin_email = 'masuma1212bd@gmail.com'

        if not g.user:
            return redirect(url_for('login'))

        # লজিক: যদি ইমেইল মিলে যায় অথবা ইউজার 'admin' হয়, তবেই ঢুকতে দিবে
        if g.user.get('email') == sub_admin_email or g.user.get('role') == 'admin':
            return f(*args, **kwargs)

        flash("⛔ আপনার এই পেজে প্রবেশ করার অনুমতি নেই!", "error")
        return redirect(url_for('dashboard'))
        
    return decorated_function
# --- HELPER: FATEMA & ADMIN ACCESS DECORATOR ---
def fatema_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        allowed_email = 'fatemaaktersamiya2@gmail.com'
        if not g.user:
            return redirect(url_for('login'))
        
        # যদি ইউজার এডমিন হয় অথবা ফাতেমা হয়, তবেই ঢুকতে দিবে
        if g.user.get('email') == allowed_email or g.user.get('role') == 'admin':
            return f(*args, **kwargs)
            
        flash("⛔ আপনার এই পেজে প্রবেশ করার অনুমতি নেই!", "error")
        return redirect(url_for('dashboard'))
    return decorated_function
# -------------------------------------------------------------------
# 4. ROUTES
# -------------------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')
    
    # --- ADMIN: ADVANCED CUSTOM FILTER (DYNAMIC) ---
# --- ADMIN: MANAGE DRIVE PACKS --

# ==========================================
# NEWBIE CHECK PANEL (1st & 2nd Task Only)
# ==========================================
@app.route('/aw/newbie-check')
@login_required
@fatema_admin_required
def newbie_check():
    # ১. সব পেন্ডিং সাবমিশন নিয়ে আসা
    try:
        pending_subs = supabase.table('submissions').select('*').eq('status', 'pending').order('created_at', desc=True).execute().data
        
        valid_subs =[]
        
        # ২. চেক করা কোনটি ১ম বা ২য় সাবমিশন
        for sub in pending_subs:
            # এই ইউজারের সব সাবমিশন (পুরনো থেকে নতুন)
            user_all_subs = supabase.table('submissions').select('id').eq('user_id', sub['user_id']).order('created_at').execute().data
            
            # প্রথম ২ টি সাবমিশনের আইডি নেওয়া
            first_two_ids = [s['id'] for s in user_all_subs[:2]]
            
            # যদি বর্তমান পেন্ডিং আইডিটি প্রথম দুটির মধ্যে থাকে
            if sub['id'] in first_two_ids:
                try:
                    # সাবমিশনটি কত নাম্বার তা বের করা (1 or 2)
                    attempt_num = first_two_ids.index(sub['id']) + 1
                    sub['attempt_num'] = attempt_num
                    
                    # ইউজার এবং টাস্কের তথ্য যুক্ত করা
                    user_info = supabase.table('profiles').select('email').eq('id', sub['user_id']).single().execute().data
                    task_info = supabase.table('tasks').select('title, reward').eq('id', sub['task_id']).single().execute().data
                    
                    sub['user_email'] = user_info['email']
                    sub['task_title'] = task_info['title']
                    sub['reward'] = task_info['reward']
                    
                    valid_subs.append(sub)
                except:
                    continue
                    
    except Exception as e:
        print(f"Newbie Check Error: {e}")
        valid_subs =[]

    return render_template('newbie_check.html', submissions=valid_subs)

# --- ACTION: APPROVE / REJECT FOR NEWBIE PANEL ---
@app.route('/aw/newbie-action/<action>/<int:sub_id>')
@login_required
@fatema_admin_required
def newbie_action(action, sub_id):
    try:
        sub_res = supabase.table('submissions').select('*').eq('id', sub_id).single().execute()
        submission = sub_res.data
        
        if submission['status'] == 'approved':
            flash("⚠️ এটি আগেই অ্যাপ্রুভ করা হয়েছে!", "warning")
            return redirect(url_for('newbie_check'))

        if action == 'approve':
            task_res = supabase.table('tasks').select('reward').eq('id', submission['task_id']).single().execute()
            reward = float(task_res.data['reward'])
            
            user_res = supabase.table('profiles').select('balance').eq('id', submission['user_id']).single().execute()
            current_balance = float(user_res.data['balance']) if user_res.data['balance'] else 0.0
            
            new_balance = current_balance + reward
            
            supabase.table('profiles').update({'balance': new_balance}).eq('id', submission['user_id']).execute()
            supabase.table('submissions').update({'status': 'approved'}).eq('id', sub_id).execute()
            flash(f"✅ অ্যাপ্রুভ সফল! ৳{reward} যোগ হয়েছে।", "success")

        elif action == 'reject':
            supabase.table('submissions').update({'status': 'rejected'}).eq('id', sub_id).execute()
            flash("❌ রিজেক্ট করা হয়েছে।", "error")

    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for('newbie_check'))
    
@app.route('/admin/drive/manage', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_drive_manage():
    # প্যাক অ্যাড করা
    if request.method == 'POST':
        operator = request.form.get('operator')
        title = request.form.get('title')
        category = request.form.get('category')
        regular_price = request.form.get('regular_price')
        offer_price = request.form.get('offer_price')
        validity = request.form.get('validity')
        
        # Commission Calculation (Optional display)
        diff = float(regular_price) - float(offer_price)
        commission = f"{int((diff / float(regular_price)) * 100)}%"

        supabase.table('drive_packs').insert({
            'operator': operator,
            'title': title,
            'category': category,
            'regular_price': regular_price,
            'offer_price': offer_price,
            'commission': commission,
            'validity': validity
        }).execute()
        flash("✅ নতুন ড্রাইভ প্যাক যুক্ত হয়েছে!", "success")
        return redirect(url_for('admin_drive_manage'))

    # প্যাক লিস্ট এবং অর্ডার লিস্ট দেখানো
    packs = supabase.table('drive_packs').select('*').order('id', desc=True).execute().data
    orders = supabase.table('drive_orders').select('*').order('created_at', desc=True).execute().data
    
    # অর্ডারের সাথে প্যাক ডিটেইলস মার্জ করা (Display purpose)
    final_orders = []
    for o in orders:
        try:
            pack = supabase.table('drive_packs').select('title, operator').eq('id', o['pack_id']).single().execute().data
            o['pack_title'] = pack['title']
            o['operator'] = pack['operator']
            final_orders.append(o)
        except: continue

    return render_template('admin_drive.html', packs=packs, orders=final_orders)


# --- 1. SPECIAL TASK SUBMISSION PAGE ---
@app.route('/special-task', methods=['GET', 'POST'])
@login_required
def special_task():
    # চেক করা ইউজার কি অলরেডি সাবমিট করেছে? (Pending or Approved)
    existing = supabase.table('special_submissions').select('*').eq('user_id', session['user_id']).execute().data
    
    # যদি পেন্ডিং বা অ্যাপ্রুভ থাকে, তবে ঢুকতে দিবে না
    if existing:
        status = existing[0]['status']
        if status in ['pending', 'approved']:
            flash(f"⚠️ আপনার টাস্কটি বর্তমানে {status} অবস্থায় আছে।", "warning")
            return redirect(url_for('tasks'))

    if request.method == 'POST':
        code = request.form.get('code')
        file = request.files.get('screenshot')
        
        if not file or not code:
            flash("কোড এবং স্ক্রিনশট উভয়ই প্রয়োজন!", "error")
            return redirect(request.url)

        try:
            # ImgBB Upload
            api_key = "2d69b70f4a3a8f863e63b82a896446bf"
            image_string = base64.b64encode(file.read())
            payload = { "key": api_key, "image": image_string }
            response = requests.post("https://api.imgbb.com/1/upload", data=payload)
            data = response.json()
            
            if data['success']:
                img_url = data['data']['url']
                
                # Save to DB
                supabase.table('special_submissions').insert({
                    'user_id': session['user_id'],
                    'code': code,
                    'proof_link': img_url,
                    'status': 'pending'
                }).execute()
                
                flash("✅ স্পেশাল টাস্ক জমা হয়েছে!", "success")
                return redirect(url_for('tasks'))
            else:
                flash("Image upload failed", "error")
                
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    return render_template('special_task.html', task=SPECIAL_TASK_INFO, user=g.user)
# --- SPECIAL VIDEO PAGE (/st) ---
@app.route('/st')
def special_video_page():
    # লগিন ছাড়াও দেখা যাবে, তবে লগিন থাকলে মেনু ঠিক থাকবে
    return render_template('st.html', user=g.user if 'user' in g else None)
# --- WITHDRAW ROUTE (VIP MAIN BALANCE BYPASS) ---
@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    
    # ১. এক্টিভেশন সিকিউরিটি চেক
    if g.settings.get('activation_required'):
        if not g.user.get('is_active') and g.user.get('role') != 'admin':
            flash("⚠️ টাকা উত্তোলনের জন্য আগে একাউন্ট ভেরিফাই করুন!", "error")
            return redirect(url_for('activate_account'))

    # ২. পেমেন্ট মেথড সেটআপ চেক
    if not g.user.get('wallet_number') or not g.user.get('wallet_method'):
        flash("⚠️ টাকা তোলার আগে পেমেন্ট মেথড (বিকাশ/নগদ) সেট আপ করুন।", "warning")
        return redirect(url_for('adm_settings'))

    # ৩. রেফারেল সংখ্যা গণনা
    try:
        response = supabase.table('profiles').select('id').eq('referred_by', session['user_id']).execute()
        ref_count = len(response.data)
    except Exception as e:
        ref_count = 0

    # ৪. একাউন্টের বয়স বের করা
    account_days = 0
    try:
        from datetime import datetime, timezone
        join_str = g.user.get('created_at')
        if join_str:
            join_date = datetime.fromisoformat(join_str.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            delta = current_time - join_date
            account_days = delta.days
    except: pass

    # ৫. ব্যালেন্স এবং লেভেল লোড
    main_balance = float(g.user.get('balance', 0.0))
    vip_balance = float(g.user.get('vip_balance', 0.0))
    user_level = g.user.get('current_level', 0)

    # ৬. উইথড্র প্রসেস (POST Request)
    if request.method == 'POST':
        wallet_type = request.form.get('wallet_type') # main or vip
        try:
            amount = float(request.form.get('amount'))
        except:
            amount = 0

        # --- লজিক আলাদা করা ---
        if wallet_type == 'main':
            # 🔴 ফ্রি ইউজারদের জন্য কঠিন শর্ত
            if user_level == 0:
                if ref_count < 3:
                    flash("❌ ফ্রি ইউজারদের ৩টি রেফার প্রয়োজন।", "error")
                    return redirect(url_for('withdraw'))
                if account_days < 1:
                    flash("❌ আপনার একাউন্টের বয়স ১ দিন হতে হবে।", "error")
                    return redirect(url_for('withdraw'))
                if amount < 300:
                    flash("❌ ফ্রি ইউজারদের মেইন ব্যালেন্স থেকে সর্বনিম্ন উইথড্রয়াল ৩০০ টাকা।", "error")
                    return redirect(url_for('withdraw'))
            # 🟢 VIP ইউজারদের জন্য সহজ শর্ত (মেইন ব্যালেন্স)
            else:
                if amount < 50:
                    flash("❌ VIP ইউজারদের মেইন ব্যালেন্স থেকে সর্বনিম্ন উইথড্রয়াল ৫০ টাকা।", "error")
                    return redirect(url_for('withdraw'))
            
            # ব্যালেন্স চেক (সবার জন্য)
            if amount > main_balance:
                flash("❌ মেইন ব্যালেন্সে পর্যাপ্ত টাকা নেই।", "error")
                return redirect(url_for('withdraw'))
                
            # টাকা কাটা (Main)
            new_bal = main_balance - amount
            supabase.table('profiles').update({'balance': new_bal}).eq('id', session['user_id']).execute()

        elif wallet_type == 'vip':
            # 🟡 ভিআইপি ব্যালেন্স থেকে উইথড্র (কোনো রেফার বা বয়সের শর্ত নেই)
            if amount < 50:
                flash("❌ ভিআইপি ব্যালেন্স থেকে মিনিমাম ৫০ টাকা তুলতে হবে।", "error")
                return redirect(url_for('withdraw'))
            if amount > vip_balance:
                flash("❌ ভিআইপি ব্যালেন্সে পর্যাপ্ত টাকা নেই।", "error")
                return redirect(url_for('withdraw'))
            
            # টাকা কাটা (VIP)
            new_bal = vip_balance - amount
            supabase.table('profiles').update({'vip_balance': new_bal}).eq('id', session['user_id']).execute()
            
        else:
            flash("ভুল ওয়ালেট টাইপ!", "error")
            return redirect(url_for('withdraw'))

        # --- রিকোয়েস্ট ডাটাবেসে সেভ ---
        try:
            supabase.table('withdrawals').insert({
                'user_id': session['user_id'],
                'method': g.user.get('wallet_method'),
                'number': g.user.get('wallet_number'),
                'amount': amount,
                'wallet_type': wallet_type,
                'status': 'pending'
            }).execute()

            flash(f"✅ {wallet_type.upper()} ব্যালেন্স থেকে উইথড্র সফল!", "success")
            return redirect(url_for('history'))

        except Exception as e:
            flash(f"System Error: {str(e)}", "error")

    # ৭. পেজ রেন্ডার
    return render_template('withdraw.html', 
                           user=g.user, 
                           ref_count=ref_count, 
                           account_days=account_days,
                           settings=g.settings)
# --- 2. SUB-ADMIN PANEL (/aw/result) ---
@app.route('/aw/result')
@login_required
@sub_admin_required  # <--- Only Masuma access
def aw_result():
    # পেন্ডিং রিকোয়েস্ট আনা
    try:
        res = supabase.table('special_submissions').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
        submissions = res.data
        
        # ইউজার ইমেইল যুক্ত করা
        final_data = []
        for sub in submissions:
            user = supabase.table('profiles').select('email').eq('id', sub['user_id']).single().execute().data
            sub['user_email'] = user['email']
            final_data.append(sub)
            
    except:
        final_data = []

    return render_template('aw_result.html', submissions=final_data)
    # --- VIP PAGE (MULTIPLE PLANS & CLAIM LOGIC) ---
@app.route('/vip', methods=['GET', 'POST'])
@login_required
def vip_page():
    from datetime import datetime, timezone
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'claim':
            vip_id = request.form.get('vip_id') 
            
            # ১. প্যাকেজটি ডাটাবেস থেকে আনা
            vip_res = supabase.table('user_vips').select('*').eq('id', vip_id).eq('user_id', session['user_id']).single().execute()
            vip_data = vip_res.data
            
            if not vip_data or vip_data['status'] != 'active':
                flash("⚠️ প্যাকেজটি পাওয়া যায়নি বা মেয়াদ শেষ।", "error")
                return redirect(url_for('vip_page'))

            # ২. মেয়াদ চেক করা
            expiry_date = datetime.fromisoformat(vip_data['expires_at'].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expiry_date:
                supabase.table('user_vips').update({'status': 'expired'}).eq('id', vip_id).execute()
                flash("❌ এই প্যাকেজটির মেয়াদ শেষ হয়ে গেছে।", "error")
                return redirect(url_for('vip_page'))

            # ৩. আজকের ডেট চেক (আজকে কি ক্লেইম করেছে?)
            if vip_data['last_claim'] == today_str:
                flash("⚠️ এই প্যাকেজের আজকের প্রফিট ইতিমধ্যে নেওয়া হয়েছে!", "warning")
                return redirect(url_for('vip_page'))

            # ৪. টাকা VIP Balance এ যোগ করা
            profit = float(vip_data['profit'])
            current_vip_balance = float(g.user.get('vip_balance', 0.0))
            new_vip_balance = current_vip_balance + profit
            
            supabase.table('profiles').update({'vip_balance': new_vip_balance}).eq('id', session['user_id']).execute()
            supabase.table('user_vips').update({'last_claim': today_str}).eq('id', vip_id).execute()
            
            flash(f"🎉 ৳{profit} প্রফিট যোগ হয়েছে!", "success")
            return redirect(url_for('vip_page'))

    # GET Method: ইউজারের সব 'active' প্যাকেজগুলো আনা
    my_vips =[]
    try:
        res = supabase.table('user_vips').select('*').eq('user_id', session['user_id']).eq('status', 'active').order('created_at', desc=False).execute()
        my_vips = res.data
    except Exception as e:
        print(f"VIP Fetch Error: {e}")

    return render_template('vip.html', user=g.user, plans=VIP_PLANS, my_vips=my_vips, today_date=today_str)
# --- BUY VIP (SUBMIT PROOF) ---
@app.route('/vip/buy/<int:level_id>', methods=['GET', 'POST'])
@login_required
def vip_buy(level_id):
    plan = VIP_PLANS.get(level_id)
    
    if request.method == 'POST':
        method = request.form.get('method')
        number = request.form.get('sender')
        trx_id = request.form.get('trx_id')
        
        try:
            supabase.table('vip_requests').insert({
                'user_id': session['user_id'],
                'level_id': level_id,
                'amount': plan['price'],
                'method': method,
                'number': number,
                'trx_id': trx_id,
                'status': 'pending'
            }).execute()
            
            flash("✅ রিকোয়েস্ট জমা হয়েছে! এডমিন চেক করে আপগ্রেড করে দিবে।", "success")
            return redirect(url_for('vip_page'))
        except Exception as e:
            flash(f"Error: {e}", "error")

    return render_template('vip_buy.html', plan=plan)

# --- ADMIN: VIP REQUESTS ---
@app.route('/admin/vip')
@login_required
@admin_required
def admin_vip():
    reqs = supabase.table('vip_requests').select('*').eq('status', 'pending').order('created_at', desc=True).execute().data
    
    # ইউজার ইনফো মার্জ
    final_data = []
    for r in reqs:
        try:
            u = supabase.table('profiles').select('email, referred_by').eq('id', r['user_id']).single().execute().data
            r['user_email'] = u['email']
            r['referred_by'] = u['referred_by']
            final_data.append(r)
        except: continue
        
    return render_template('admin_vip.html', requests=final_data)
    
# --- 3. SUB-ADMIN ACTION (Approve/Reject) ---
@app.route('/aw/action/<action>/<int:id>')
@login_required
@sub_admin_required
def aw_action(action, id):
    try:
        sub_res = supabase.table('special_submissions').select('*').eq('id', id).single().execute()
        submission = sub_res.data
        
        if not submission: return redirect(url_for('aw_result'))

        if action == 'approve':
            # ব্যালেন্স অ্যাড করা
            user_res = supabase.table('profiles').select('balance').eq('id', submission['user_id']).single().execute()
            new_bal = float(user_res.data['balance']) + SPECIAL_TASK_INFO['reward']
            
            supabase.table('profiles').update({'balance': new_bal}).eq('id', submission['user_id']).execute()
            supabase.table('special_submissions').update({'status': 'approved'}).eq('id', id).execute()
            flash("✅ Approved & Paid!", "success")
            
        elif action == 'reject':
            # রিজেক্ট করলে ইউজার আবার সাবমিট করতে পারবে
            supabase.table('special_submissions').update({'status': 'rejected'}).eq('id', id).execute()
            flash("❌ Rejected.", "warning")
            
    except Exception as e:
        flash(f"Error: {e}", "error")

    return redirect(url_for('aw_result'))


# --- USER: DRIVE ORDER HISTORY ---
@app.route('/drive/history')
@login_required
def drive_history():
    try:
        # ১. ইউজারের অর্ডার লিস্ট আনা (নতুন আগে)
        orders = supabase.table('drive_orders').select('*').eq('user_id', session['user_id']).order('created_at', desc=True).execute().data
        
        # ২. প্যাকের ডিটেইলস (নাম, দাম) যুক্ত করা
        final_orders = []
        for order in orders:
            try:
                # প্যাক আইডি দিয়ে প্যাকের তথ্য আনা
                pack = supabase.table('drive_packs').select('title, operator, offer_price').eq('id', order['pack_id']).single().execute().data
                
                order['pack_title'] = pack['title']
                order['operator'] = pack['operator']
                order['price'] = pack['offer_price']
                final_orders.append(order)
            except:
                # যদি এডমিন প্যাক ডিলিট করে দেয়
                order['pack_title'] = "Unknown Pack"
                order['operator'] = "N/A"
                order['price'] = "0"
                final_orders.append(order)
                
    except Exception as e:
        print(f"History Error: {e}")
        final_orders = []

    return render_template('drive_history.html', orders=final_orders)
# --- ADMIN: APPROVE DRIVE ORDER ---
@app.route('/admin/drive/action/<action>/<int:id>')
@login_required
@admin_required
def drive_action(action, id):
    status = 'success' if action == 'approve' else 'canceled'
    supabase.table('drive_orders').update({'status': status}).eq('id', id).execute()
    flash(f"অর্ডার স্ট্যাটাস: {status}", "info")
    return redirect(url_for('admin_drive_manage'))

# --- USER: DRIVE STORE (VIEW PACKS) ---
@app.route('/drive')
@login_required
def drive_store():
    # সব অ্যাক্টিভ প্যাক আনা
    packs = supabase.table('drive_packs').select('*').eq('is_active', True).order('id', desc=True).execute().data
    return render_template('drive.html', packs=packs)

# --- USER: BUY PACK (CHECKOUT) ---
@app.route('/drive/buy/<int:id>', methods=['GET', 'POST'])
@login_required
def drive_buy(id):
    # প্যাক ডিটেইলস
    pack = supabase.table('drive_packs').select('*').eq('id', id).single().execute().data
    
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        method = request.form.get('method')
        sender = request.form.get('sender')
        trx_id = request.form.get('trx_id')
        
        supabase.table('drive_orders').insert({
            'user_id': session['user_id'],
            'pack_id': id,
            'mobile_number': mobile,
            'payment_method': method,
            'sender_number': sender,
            'trx_id': trx_id,
            'status': 'pending'
        }).execute()
        
        flash("✅ অর্ডার সফল! এডমিন চেক করে অফারটি চালু করে দিবেন।", "success")
        return redirect(url_for('drive_store'))
        
    return render_template('drive_checkout.html', pack=pack)
    
# --- DAILY CHECK-IN BONUS ---
@app.route('/daily-checkin')
@login_required
def daily_checkin():
    from datetime import datetime, timedelta
    
    try:
        # ১. বর্তমান তারিখ বের করা (UTC)
        today = datetime.utcnow().date()
        
        # ২. ইউজার ডাটা আনা
        user_res = supabase.table('profiles').select('last_checkin, streak_count, balance').eq('id', session['user_id']).single().execute()
        user_data = user_res.data
        
        last_checkin_str = user_data.get('last_checkin')
        current_streak = user_data.get('streak_count', 0)
        current_balance = float(user_data.get('balance', 0.0))
        
        # ৩. তারিখ কনভার্ট করা
        last_checkin = datetime.strptime(last_checkin_str, '%Y-%m-%d').date() if last_checkin_str else None
        
        # --- লজিক চেক ---
        
        # ক. যদি আজকেই নিয়ে থাকে
        if last_checkin == today:
            flash("⚠️ আপনি আজকের বোনাস ইতিমধ্যে নিয়ে নিয়েছেন!", "warning")
            return redirect(url_for('dashboard'))
            
        # খ. স্ট্রিক ক্যালকুলেশন
        # যদি গতকাল নিয়ে থাকে, তাহলে স্ট্রিক বাড়বে। না হলে ১ থেকে শুরু হবে।
        if last_checkin == today - timedelta(days=1):
            new_streak = current_streak + 1
        else:
            new_streak = 1 # মিস করলে রিসেট
            
        # ৭ দিনের সাইকেল শেষ হলে আবার ১ থেকে শুরু (অথবা ৩০ টাকায় ফিক্সড রাখতে পারেন)
        if new_streak > 7:
            new_streak = 1
            
        # গ. রিওওার্ড ম্যাপ (কোন দিন কত টাকা)
        rewards = {
            1: 5.00,
            2: 7.00,
            3: 15.00,
            4: 18.00,
            5: 22.00,
            6: 25.00,
            7: 30.00
        }
        
        bonus_amount = rewards.get(new_streak, 5.00)
        
        # ৪. ডাটাবেস আপডেট
        new_balance = current_balance + bonus_amount
        
        supabase.table('profiles').update({
            'balance': new_balance,
            'streak_count': new_streak,
            'last_checkin': str(today)
        }).eq('id', session['user_id']).execute()
        
        flash(f"🎉 অভিনন্দন! ডে-{new_streak} এর বোনাস ৳{bonus_amount} যোগ হয়েছে!", "success")
        
    except Exception as e:
        print(f"Checkin Error: {e}")
        flash("System Error. Try again later.", "error")
        
    return redirect(url_for('dashboard'))
@app.route('/admin/custom-filter', methods=['GET', 'POST'])
@login_required
@admin_required
def custom_filter():
    csv_data = ""
    count = 0
    filters = {} # ফর্মের ভ্যালুগুলো মনে রাখার জন্য

    if request.method == 'POST':
        try:
            # ১. ফর্ম থেকে ডাটা নেওয়া
            min_bal = request.form.get('min_balance')
            max_bal = request.form.get('max_balance')
            days_offline = request.form.get('days_offline')
            email_domain = request.form.get('email_domain')
            limit_num = request.form.get('limit', 290)

            # ডাটা মনে রাখার জন্য ডিকশনারিতে রাখা
            filters = {
                'min': min_bal, 'max': max_bal, 
                'days': days_offline, 'domain': email_domain, 'limit': limit_num
            }

            # ২. কুয়েরি বিল্ড করা (ধাপে ধাপে)
            query = supabase.table('profiles').select('email')

            # ব্যালেন্স ফিল্টার
            if min_bal: query = query.gte('balance', float(min_bal))
            if max_bal: query = query.lte('balance', float(max_bal))

            # সময় ফিল্টার (Offline Days)
            if days_offline:
                target_date = (datetime.utcnow() - timedelta(days=int(days_offline))).isoformat()
                # lte মানে এই তারিখের আগে (অর্থাৎ এত দিন ধরে অফলাইন)
                query = query.lte('last_login', target_date)

            # ইমেইল ডোমেইন ফিল্টার
            if email_domain:
                query = query.ilike('email', f'%{email_domain}')

            # ৩. এক্সিকিউট করা
            res = query.limit(int(limit_num)).execute()
            users = res.data

            # ৪. CSV ফরম্যাট তৈরি
            email_list = [u['email'] for u in users]
            csv_data = ", ".join(email_list)
            count = len(email_list)

        except Exception as e:
            print(f"Custom Filter Error: {e}")
            flash(f"Error: {str(e)}", "error")

    return render_template('custom_filter.html', csv_data=csv_data, count=count, f=filters)
# --- PUBLIC: PROOFS PAGE (MULTI-UPLOAD UP TO 3) ---# --- PUBLIC: PROOFS PAGE (CAROUSEL POST) ---
@app.route('/proofs', methods=['GET', 'POST'])
def proofs():
    # ১. আপলোড লজিক (ADMIN ONLY)
    if request.method == 'POST':
        if not g.user or g.user.get('role') != 'admin':
            flash("⚠️ শুধুমাত্র এডমিন আপলোড করতে পারবে।", "error")
            return redirect(url_for('proofs'))

        files = request.files.getlist('images')
        description = request.form.get('description')

        if not files or files[0].filename == '':
            flash("কোনো ছবি সিলেক্ট করা হয়নি", "error")
            return redirect(request.url)

        uploaded_urls = []
        
        # সব ছবি একে একে ImgBB তে আপলোড করে লিংক সংগ্রহ করা
        for file in files[:3]: # Max 3 files
            if file.filename == '': continue
            try:
                api_key = "267ae03c170ebbd607e4d0dd4a2acc99"
                image_string = base64.b64encode(file.read())
                payload = { "key": api_key, "image": image_string }
                
                response = requests.post("https://api.imgbb.com/1/upload", data=payload)
                data = response.json()
                
                if data['success']:
                    uploaded_urls.append(data['data']['url'])
            except Exception as e:
                print(f"Img Upload Error: {e}")
                continue

        # যদি অন্তত একটি ছবি আপলোড হয়, তবে ডাটাবেসে সেভ করো
        if len(uploaded_urls) > 0:
            try:
                supabase.table('proofs').insert({
                    'image_urls': uploaded_urls, # পুরো লিস্ট পাঠানো হচ্ছে
                    'description': description
                }).execute()
                flash("✅ পোস্ট পাবলিশ করা হয়েছে!", "success")
            except Exception as e:
                flash(f"Database Error: {str(e)}", "error")
        else:
            flash("❌ ছবি আপলোড ব্যর্থ হয়েছে।", "error")
            
        return redirect(url_for('proofs'))

    # ২. সব প্রুফ লোড করা
    try:
        res = supabase.table('proofs').select('*').order('created_at', desc=True).execute()
        all_proofs = res.data
    except:
        all_proofs = []

    return render_template('proofs.html', proofs=all_proofs, user=g.user if 'user' in g else None)
# --- DELETE PROOF (ADMIN ONLY) ---
@app.route('/proof/delete/<int:id>')
@login_required
@admin_required
def delete_proof(id):
    try:
        supabase.table('proofs').delete().eq('id', id).execute()
        flash("🗑️ প্রুফ ডিলিট করা হয়েছে।", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        
    return redirect(url_for('proofs'))
    
# --- NOTICE BOARD ROUTE ---
@app.route('/notice', methods=['GET', 'POST'])
@login_required
def notice():
    # ১. নতুন নোটিশ পোস্ট করা (শুধুমাত্র এডমিন)
    if request.method == 'POST':
        # সিকিউরিটি চেক: এডমিন না হলে রিজেক্ট
        if g.user.get('role') != 'admin':
            flash("⚠️ শুধুমাত্র এডমিন নোটিশ দিতে পারবে।", "error")
            return redirect(url_for('notice'))

        title = request.form.get('title')
        content = request.form.get('content')

        try:
            supabase.table('notices').insert({
                'title': title,
                'content': content
            }).execute()
            flash("✅ নোটিশ পাবলিশ করা হয়েছে!", "success")
        except Exception as e:
            flash("Error publishing notice", "error")
            
        return redirect(url_for('notice'))

    # ২. সব নোটিশ লোড করা (সবার জন্য)
    try:
        res = supabase.table('notices').select('*').order('created_at', desc=True).execute()
        notices = res.data
    except:
        notices = []

    return render_template('notice.html', notices=notices, user=g.user)
# --- ADMIN: VIEW WITHDRAWAL REQUESTS (UPDATED WITH REJECT COUNT & STATUS) ---
@app.route('/admin/withdrawals')
@login_required
@admin_required
def admin_withdrawals():
    # ১. পেন্ডিং রিকোয়েস্ট আনা
    res = supabase.table('withdrawals').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
    withdrawals = res.data
    
    final_data =[]
    for item in withdrawals:
        try:
            # ২. ইউজার ইমেইল এবং এক্টিভেশন স্ট্যাটাস আনা
            user = supabase.table('profiles').select('email, is_active').eq('id', item['user_id']).single().execute().data
            item['user_email'] = user['email']
            item['is_active'] = user['is_active']

            # ৩. ইউজারের আগের রিজেক্টেড উইথড্র সংখ্যা বের করা
            reject_res = supabase.table('withdrawals').select('id', count='exact', head=True).eq('user_id', item['user_id']).eq('status', 'rejected').execute()
            item['rejected_count'] = reject_res.count if reject_res.count else 0

            final_data.append(item)
        except Exception as e:
            print(f"Withdrawal fetch error: {e}")
            continue # ইউজার ডিলিট হয়ে গেলে স্কিপ করবে

    return render_template('admin_withdrawals.html', requests=final_data)
    
# --- ADMIN: OFFLINE / INACTIVE USERS (CSV) ---
@app.route('/admin/offline-users')
@login_required
@admin_required
def admin_offline_users():
    try:
        # ১. ৭ দিন আগের তারিখ বের করা
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        
        # ২. কুয়েরি চালানো
        # শর্ত: balance 15-150, last_login <= 7 days ago, gmail only
        res = supabase.table('profiles').select('email') \
            .gte('balance', 15) \
            .lte('balance', 150) \
            .ilike('email', '%@gmail.com') \
            .lte('last_login', seven_days_ago) \
            .limit(290) \
            .execute()
            
        users = res.data
        
        # ৩. CSV ফরম্যাট তৈরি (Comma Separated)
        email_list = [u['email'] for u in users]
        csv_data = ", ".join(email_list)
        count = len(email_list)
        
    except Exception as e:
        print(f"Offline Filter Error: {e}")
        csv_data = ""
        count = 0

    return render_template('offline_users.html', csv_data=csv_data, count=count)
    
# --- PUBLIC TUTORIAL PAGE ---
@app.route('/tutorial')
def tutorial():
    # g.user পাস করছি যাতে লগিন থাকলে নেভিগেশন বার ঠিক থাকে
    # লগিন না থাকলে g.user None থাকবে (before_request হ্যান্ডেল করবে)
    return render_template('tutorial.html', user=g.user if 'user' in g else None)
    
# --- ADMIN: APPROVE / REJECT WITHDRAWAL ---
@app.route('/admin/withdraw/<action>/<int:id>')
@login_required
@admin_required
def withdraw_action(action, id):
    try:
        # ১. রিকোয়েস্ট ডিটেইলস আনা
        res = supabase.table('withdrawals').select('*').eq('id', id).single().execute()
        request_data = res.data
        
        if not request_data:
            flash("রিকোয়েস্ট পাওয়া যায়নি!", "error")
            return redirect(url_for('admin_withdrawals'))

        # ২. যদি APPROVE করা হয়
        if action == 'approve':
            supabase.table('withdrawals').update({
                'status': 'approved'
            }).eq('id', id).execute()
            
            flash("✅ উইথড্রয়াল অ্যাপ্রুভ করা হয়েছে!", "success")

        # ৩. যদি REJECT করা হয় (টাকা রিফান্ড হবে)
        elif action == 'reject':
            # A. ইউজারের বর্তমান ব্যালেন্স আনা
            user_res = supabase.table('profiles').select('balance').eq('id', request_data['user_id']).single().execute()
            current_balance = float(user_res.data['balance'])
            
            # B. টাকা ফেরত দেওয়া (Refund)
            refund_amount = float(request_data['amount'])
            new_balance = current_balance + refund_amount
            
            # C. ব্যালেন্স আপডেট
            supabase.table('profiles').update({
                'balance': new_balance
            }).eq('id', request_data['user_id']).execute()
            
            # D. স্ট্যাটাস রিজেক্ট করা
            supabase.table('withdrawals').update({
                'status': 'rejected'
            }).eq('id', id).execute()
            
            flash(f"❌ রিজেক্ট করা হয়েছে। ৳{refund_amount} রিফান্ড করা হয়েছে।", "warning")

    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for('admin_withdrawals'))

# --- ADMIN: REFERRAL CHECKER & USER INSIGHT ---
@app.route('/admin/ref-check', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_ref_check():
    target_user = None
    referrals = []
    ref_count = 0
    search_email = ""

    if request.method == 'POST':
        search_email = request.form.get('email')
        
        if search_email:
            try:
                # ১. টার্গেট ইউজারকে ইমেইল দিয়ে খোঁজা
                # ilike ব্যবহার করছি যাতে ছোট/বড় হাতের অক্ষর সমস্যা না করে
                user_res = supabase.table('profiles').select('*').ilike('email', search_email.strip()).execute()
                
                if user_res.data:
                    target_user = user_res.data[0] # প্রথম রেজাল্ট নেওয়া হলো
                    
                    # ২. তার রেফার করা মেম্বারদের খোঁজা (যাদের referred_by = target_user.id)
                    ref_res = supabase.table('profiles').select('*').eq('referred_by', target_user['id']).order('created_at', desc=True).execute()
                    referrals = ref_res.data
                    ref_count = len(referrals)
                else:
                    flash("❌ এই ইমেইলে কোনো ইউজার পাওয়া যায়নি।", "error")
                    
            except Exception as e:
                print(f"Search Error: {e}")
                flash(f"System Error: {str(e)}", "error")

    return render_template('ref_check.html', target_user=target_user, referrals=referrals, count=ref_count, search_email=search_email)
# --- REFERRALS PAGE (LOGIC UPDATED) ---
@app.route('/referrals')
@login_required
def referrals():
    try:
        # ১. আমার রেফারেল লিস্ট আনা
        res = supabase.table('profiles').select('*').eq('referred_by', session['user_id']).order('created_at', desc=True).execute()
        my_refs = res.data
        
        total_count = len(my_refs)
        
        # ২. Active Count লজিক (Settings অনুযায়ী)
        if g.settings.get('activation_required'):
            # যদি অ্যাক্টিভেশন অন থাকে, তবে শুধু Paid ইউজার গুনবে
            active_count = sum(1 for user in my_refs if user.get('is_active') == True)
        else:
            # যদি অ্যাক্টিভেশন অফ থাকে, তবে সবাইকেই Active হিসেবে গুনবে (Campaign এর জন্য)
            active_count = total_count
        
        # ৩. লিডারবোর্ড (Demo Logic)
        leaderboard = [
            {'email': 'top1@gmail.com', 'count': 450},
            {'email': 'king@yahoo.com', 'count': 320},
            {'email': 'user99@gmail.com', 'count': 150},
            {'email': 'pro_earner@gmail.com', 'count': 85},
            {'email': 'newbie@gmail.com', 'count': 40}
        ]

    except Exception as e:
        print(f"Ref Error: {e}")
        my_refs = []
        total_count = 0
        active_count = 0
        leaderboard = []

    return render_template('referrals.html', 
                           referrals=my_refs, 
                           total_count=total_count, 
                           active_count=active_count, 
                           leaderboard=leaderboard,
                           user=g.user,
                           settings=g.settings)# --- DELETE NOTICE (ADMIN ONLY) ---
@app.route('/notice/delete/<int:id>')
@login_required
@admin_required
def delete_notice(id):
    try:
        supabase.table('notices').delete().eq('id', id).execute()
        flash("🗑️ নোটিশ ডিলিট করা হয়েছে।", "success")
    except:
        flash("Error deleting notice", "error")
        
    return redirect(url_for('notice'))

# --- ADMIN: ADD TASK & VIEW LIST ---
@app.route('/adtask', methods=['GET', 'POST'])
@login_required
@admin_required
def add_task():
    # ১. নতুন টাস্ক যোগ করা (POST)
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        link = request.form.get('link')
        try:
            reward = float(request.form.get('reward'))
        except:
            reward = 0.0
        category = request.form.get('category')
        task_type = request.form.get('task_type')
        
        try:
            supabase.table('tasks').insert({
                'title': title,
                'description': description,
                'link': link,
                'reward': reward,
                'category': category,
                'task_type': task_type,
                'is_active': True
            }).execute()
            flash("✅ টাস্ক সফলভাবে যোগ করা হয়েছে!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            
        return redirect(url_for('add_task'))

    # ২. সব টাস্কের লিস্ট আনা (GET)
    try:
        # নতুন টাস্ক আগে দেখাবে
        res = supabase.table('tasks').select('*').order('id', desc=True).execute()
        all_tasks = res.data
    except:
        all_tasks = []
        
    return render_template('adtask.html', user=g.user, tasks=all_tasks)


# --- ADMIN: DELETE TASK ---
@app.route('/admin/task/delete/<int:id>')
@login_required
@admin_required
def delete_task(id):
    try:
        # A. টাস্ক ডিলিট করার আগে এর সাবমিশনগুলো ডিলিট করতে হবে (Foreign Key Error এড়াতে)
        supabase.table('submissions').delete().eq('task_id', id).execute()
        
        # B. মূল টাস্ক ডিলিট করা
        supabase.table('tasks').delete().eq('id', id).execute()
        
        flash("🗑️ টাস্ক এবং এর সাবমিশন মুছে ফেলা হয়েছে।", "success")
    except Exception as e:
        flash(f"Delete Error: {str(e)}", "error")
        
    return redirect(url_for('add_task'))
# --- ADMIN: VIEW PENDING SUBMISSIONS (LIMIT 20) ---
@app.route('/admin/submissions')
@login_required
@admin_required
@fatema_admin_required
def admin_submissions():
    # ১. মাত্র ২০টি পেন্ডিং ডাটা আনা (Performance এর জন্য)
    # .limit(20) যোগ করা হয়েছে
    subs_res = supabase.table('submissions').select('*').eq('status', 'pending').order('created_at', desc=True).limit(20).execute()
    submissions = subs_res.data
    
    # ২. ডাটা প্রসেসিং (User Email এবং Task Title বের করা)
    final_data = []
    for sub in submissions:
        try:
            # ইউজার ইনফো
            user = supabase.table('profiles').select('email').eq('id', sub['user_id']).single().execute().data
            # টাস্ক ইনফো
            task = supabase.table('tasks').select('title, reward').eq('id', sub['task_id']).single().execute().data
            
            sub['user_email'] = user['email']
            sub['task_title'] = task['title']
            sub['reward'] = task['reward']
            final_data.append(sub)
        except:
            continue 

    # টোটাল পেন্ডিং কাউন্ট চেক করা (বোঝার জন্য আরও কত বাকি আছে)
    try:
        count_res = supabase.table('submissions').select('id', count='exact', head=True).eq('status', 'pending').execute()
        total_pending = count_res.count
    except:
        total_pending = len(final_data)

    return render_template('submissions.html', submissions=final_data, total_pending=total_pending)

# --- ADMIN: BULK APPROVE (FIXED & STRICT) ---
@app.route('/admin/submissions/bulk-approve')
@login_required
@admin_required
@fatema_admin_required
def bulk_approve():
    try:
        # ১. ২০টি পেন্ডিং সাবমিশন আনা
        subs_res = supabase.table('submissions').select('*').eq('status', 'pending').limit(20).execute()
        submissions = subs_res.data
        
        if not submissions:
            flash("⚠️ কোনো পেন্ডিং টাস্ক পাওয়া যায়নি।", "warning")
            return redirect(url_for('admin_submissions'))

        success_count = 0
        
        # ২. লুপ চালিয়ে কাজ করা
        for sub in submissions:
            try:
                # A. টাস্কের টাকার পরিমাণ জানা
                task_res = supabase.table('tasks').select('reward').eq('id', sub['task_id']).single().execute()
                if not task_res.data: continue # টাস্ক না পেলে স্কিপ
                reward = float(task_res.data['reward'])
                
                # B. ইউজারের বর্তমান ব্যালেন্স জানা
                user_res = supabase.table('profiles').select('balance').eq('id', sub['user_id']).single().execute()
                if not user_res.data: continue # ইউজার না পেলে স্কিপ
                current_balance = float(user_res.data['balance'])
                
                # C. নতুন ব্যালেন্স আপডেট করা
                new_balance = current_balance + reward
                supabase.table('profiles').update({'balance': new_balance}).eq('id', sub['user_id']).execute()
                
                # D. সাবমিশন স্ট্যাটাস 'approved' করা (Critial Step)
                update_res = supabase.table('submissions').update({'status': 'approved'}).eq('id', sub['id']).execute()
                
                # চেক করা: আসলেই আপডেট হয়েছে কিনা?
                if len(update_res.data) > 0:
                    success_count += 1
                    
            except Exception as loop_e:
                print(f"Error for sub {sub['id']}: {loop_e}")
                continue

        # ৩. ফলাফল জানানো
        if success_count > 0:
            flash(f"✅ সফলভাবে {success_count}টি টাস্ক অ্যাপ্রুভ এবং টাকা যোগ করা হয়েছে!", "success")
        else:
            flash("❌ সার্ভার এরর: ডাটাবেস আপডেট হয়নি। ম্যানুয়ালি চেষ্টা করুন।", "error")

    except Exception as e:
        flash(f"System Error: {str(e)}", "error")

    return redirect(url_for('admin_submissions'))



# --- ADMIN: FILTER NEW USERS (CSV COPY) ---
@app.route('/admin/user-check')
@login_required
@admin_required
def admin_user_check():
    try:
        # ১. গত ২৪ ঘন্টার সময় বের করা (UTC Time)
        last_24_hours = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        
        # ২. কুয়েরি চালানো
        # শর্ত: balance 10-50, created_at >= 24h, email contains @gmail.com
        res = supabase.table('profiles').select('email') \
            .gte('balance', 10) \
            .lte('balance', 50) \
            .gte('created_at', last_24_hours) \
            .ilike('email', '%@gmail.com') \
            .limit(290) \
            .execute()
            
        users = res.data
        
        # ৩. শুধু ইমেইলগুলো কমা (,) দিয়ে আলাদা করে স্ট্রিং বানানো (CSV Format)
        email_list = [u['email'] for u in users]
        csv_data = ", ".join(email_list)
        count = len(email_list)
        
    except Exception as e:
        print(f"Filter Error: {e}")
        csv_data = ""
        count = 0

    return render_template('user_check.html', csv_data=csv_data, count=count)# --- ADMIN: APPROVE / REJECT ACTION (FIXED) ---
@app.route('/admin/submission/<action>/<int:sub_id>')
@login_required
@admin_required
@fatema_admin_required
def submission_action(action, sub_id):
    try:
        # ১. সাবমিশন ডিটেইলস খুঁজে বের করা
        sub_res = supabase.table('submissions').select('*').eq('id', sub_id).single().execute()
        submission = sub_res.data
        
        if not submission:
            flash("❌ সাবমিশন পাওয়া যায়নি!", "error")
            return redirect(url_for('admin_submissions'))

        # ২. ডাবল পেমেন্ট আটকানো (যদি অলরেডি অ্যাপ্রুভড থাকে)
        if submission['status'] == 'approved':
            flash("⚠️ এটি আগেই অ্যাপ্রুভ করা হয়েছে!", "warning")
            return redirect(url_for('admin_submissions'))

        # ৩. যদি একশন 'approve' হয়
        if action == 'approve':
            # A. টাস্কের টাকার পরিমাণ জানা
            task_res = supabase.table('tasks').select('reward').eq('id', submission['task_id']).single().execute()
            reward = float(task_res.data['reward'])
            
            # B. ইউজারের বর্তমান ব্যালেন্স জানা
            user_res = supabase.table('profiles').select('balance').eq('id', submission['user_id']).single().execute()
            # ব্যালেন্স যদি NULL থাকে তবে 0 ধরবে
            current_balance = float(user_res.data['balance']) if user_res.data['balance'] else 0.0
            
            # C. নতুন ব্যালেন্স হিসাব করা
            new_balance = current_balance + reward
            
            # D. প্রোফাইল টেবিলে ব্যালেন্স আপডেট করা
            supabase.table('profiles').update({
                'balance': new_balance
            }).eq('id', submission['user_id']).execute()
            
            # E. সাবমিশন স্ট্যাটাস 'approved' করা
            supabase.table('submissions').update({
                'status': 'approved'
            }).eq('id', sub_id).execute()
            
            flash(f"✅ অ্যাপ্রুভ সফল! ইউজার ৳{reward} পেয়েছে।", "success")

        # ৪. যদি একশন 'reject' হয়
        elif action == 'reject':
            supabase.table('submissions').update({
                'status': 'rejected'
            }).eq('id', sub_id).execute()
            flash("❌ রিজেক্ট করা হয়েছে।", "error")

    except Exception as e:
        print(f"Error: {e}") # Vercel Logs এ এরর দেখার জন্য
        flash(f"ত্রুটি হয়েছে: {str(e)}", "error")

    return redirect(url_for('admin_submissions'))
    

@app.route('/admin/userx', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_userx():
    users = []
    csv_data = ""
    filters = {} # ফর্মের ভ্যালু ধরে রাখার জন্য
    stats = {'count': 0, 'total_balance': 0}

    if request.method == 'POST':
        try:
            # ১. ইনপুট নেওয়া
            status = request.form.get('status') # all, active, inactive, banned
            min_bal = request.form.get('min_balance')
            max_bal = request.form.get('max_balance')
            offline_days = request.form.get('offline_days')
            join_start = request.form.get('join_start')
            join_end = request.form.get('join_end')

            # ভ্যালুগুলো সেভ রাখা (HTML এ দেখানোর জন্য)
            filters = {
                'status': status, 'min_bal': min_bal, 'max_bal': max_bal,
                'offline_days': offline_days, 'join_start': join_start, 'join_end': join_end
            }

            # ২. কুয়েরি তৈরি করা
            query = supabase.table('profiles').select('*')

            # Status Filter
            if status == 'active': query = query.eq('is_active', True)
            elif status == 'inactive': query = query.eq('is_active', False)
            elif status == 'banned': query = query.eq('is_banned', True)

            # Balance Filter
            if min_bal: query = query.gte('balance', float(min_bal))
            if max_bal: query = query.lte('balance', float(max_bal))

            # Offline Filter (Last Login <= N days ago)
            if offline_days:
                from datetime import datetime, timedelta
                target_date = (datetime.utcnow() - timedelta(days=int(offline_days))).isoformat()
                query = query.lte('last_login', target_date)

            # Join Date Filter
            if join_start: query = query.gte('created_at', join_start)
            if join_end: 
                # শেষ তারিখের রাত পর্যন্ত ধরার জন্য
                query = query.lte('created_at', f"{join_end}T23:59:59")

            # ৩. এক্সিকিউট (Max 1000 data)
            res = query.limit(1000).execute()
            users = res.data

            # ৪. স্ট্যাটস এবং CSV তৈরি
            if users:
                stats['count'] = len(users)
                stats['total_balance'] = sum(float(u['balance']) for u in users)
                
                email_list = [u['email'] for u in users]
                csv_data = ", ".join(email_list)

        except Exception as e:
            print(f"UserX Error: {e}")
            flash(f"Error: {str(e)}", "error")

    return render_template('userx.html', users=users, csv_data=csv_data, f=filters, stats=stats)
# --- USER: PAYMENT SETTINGS (ADM) ---
@app.route('/adm', methods=['GET', 'POST'])
@login_required
def adm_settings():
    if request.method == 'POST':
        method = request.form.get('method')
        number = request.form.get('number')
        
        try:
            # ডাটাবেসে আপডেট করা
            supabase.table('profiles').update({
                'wallet_method': method,
                'wallet_number': number
            }).eq('id', session['user_id']).execute()
            
            flash("✅ পেমেন্ট মেথড সফলভাবে সেভ হয়েছে!", "success")
            return redirect(url_for('withdraw')) # সেভ হলে উইথড্র পেজে পাঠাবে
            
        except Exception as e:
            flash("Error updating settings", "error")

    return render_template('adm.html', user=g.user)
    
@app.route('/task/submit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def submit_task(task_id):
    # টাস্ক ডিটেইলস আনা
    try:
        task_res = supabase.table('tasks').select('*').eq('id', task_id).single().execute()
        task = task_res.data
    except:
        flash("টাস্ক পাওয়া যায়নি।", "error")
        return redirect(url_for('tasks'))

    # ১. [NEW] চেক করা: ইউজার কি আগেই এই টাস্ক সাবমিট করেছে?
    existing_sub = supabase.table('submissions').select('id').eq('user_id', session['user_id']).eq('task_id', task_id).execute()
    
    if len(existing_sub.data) > 0:
        flash("⚠️ আপনি ইতিমধ্যে এই কাজটি জমা দিয়েছেন!", "warning")
        return redirect(url_for('tasks'))

    if request.method == 'POST':
        if 'screenshot' not in request.files:
            flash("ছবি আপলোড করুন!", "error")
            return redirect(request.url)
            
        file = request.files['screenshot']
        if file.filename == '':
            flash("কোনো ছবি সিলেক্ট করা হয়নি", "error")
            return redirect(request.url)

        try:
            # ২. ImgBB তে আপলোড করা
            api_key = "d80f5947ecaed4ff46d1f3b294ab80e1" 
            image_string = base64.b64encode(file.read())
            
            payload = {
                "key": api_key,
                "image": image_string,
            }
            
            response = requests.post("https://api.imgbb.com/1/upload", data=payload)
            data = response.json()
            
            if data['success']:
                img_url = data['data']['url']
                
                # ৩. ডাটাবেসে সেভ করা
                supabase.table('submissions').insert({
                    'user_id': session['user_id'],
                    'task_id': task_id,
                    'proof_link': img_url,
                    'status': 'pending'
                }).execute()
                
                flash("✅ সফলভাবে জমা হয়েছে! এডমিন চেক করে পেমেন্ট দিবে।", "success")
                return redirect(url_for('tasks'))
            else:
                flash("❌ ছবি আপলোড ব্যর্থ হয়েছে।", "error")
                
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    return render_template('submit_task.html', task=task, user=g.user)# --- ACCOUNT PAGE ROUTE (WITH REFERRAL COUNT) ---
@app.route('/account')
@login_required
def account():
    # ১. রেফারেল সংখ্যা গণনা (Fix)
    try:
        # ডাটাবেস থেকে চেক করছি কতজন ইউজারের 'referred_by' আমার ID
        response = supabase.table('profiles').select('id').eq('referred_by', session['user_id']).execute()
        
        # লিস্টের দৈর্ঘ্যই হলো মোট রেফারেল সংখ্যা
        ref_count = len(response.data)
        
    except Exception as e:
        # কোনো এরর হলে ০ দেখাবে
        print(f"Account Page Error: {e}")
        ref_count = 0

    # ২. টেমপ্লেট রেন্ডার করা (ref_count পাস করা হলো)
    return render_template('account.html', user=g.user, settings=g.settings, ref_count=ref_count)
# --- LOGIN ROUTE (SET PERMANENT COOKIE) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    # যদি সেশন থাকে তবে ড্যাশবোর্ডে পাঠাও
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # ১. লগিন চেক
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            
            session.permanent = True
            session['user_id'] = res.user.id
            session['access_token'] = res.session.access_token
            
            # ২. লাস্ট লগিন আপডেট
            try:
                from datetime import datetime
                supabase.table('profiles').update({'last_login': datetime.now().isoformat()}).eq('id', res.user.id).execute()
            except: pass
            
            flash("✅ স্বাগতম!", "success")
            
            # ৩. [NEW] রেসপন্স তৈরি করে কুকি সেট করা (১ বছরের জন্য)
            response = make_response(redirect(url_for('dashboard')))
            # কুকির নাম 'saved_email', ভ্যালু 'email', মেয়াদ ১ বছর (31536000 সেকেন্ড)
            response.set_cookie('saved_email', email, max_age=31536000)
            
            return response
            
        except Exception as e:
            if "Email not confirmed" in str(e):
                flash("⚠️ আপনার ইমেইল ভেরিফাই করা হয়নি।", "warning")
            else:
                flash("❌ ইমেইল বা পাসওয়ার্ড ভুল হয়েছে।", "error")
            
    return render_template('login.html')
    # --- REGISTER ROUTE (BLOCK IF COOKIE EXISTS) ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    # ১. [NEW] চেক করা ব্রাউজারে আগে কোনো একাউন্ট লগিন ছিল কিনা
    existing_email = request.cookies.get('saved_email')
    
    if existing_email:
        flash(f"⚠️ এই ডিভাইসে ইতিমধ্যে একটি একাউন্ট আছে: ({existing_email})। দয়া করে লগিন করুন।", "warning")
        return redirect(url_for('login'))

    # বাকি কোড আগের মতোই...
    if request.method == 'GET':
        ref_code = request.args.get('ref')
        return render_template('register.html', ref_code=ref_code)

    if request.method == 'POST':
        full_name = request.form.get('name')
        mobile_number = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')
        used_ref_code = request.form.get('ref_code')
        
        try:
            res = supabase.auth.sign_up({
                "email": email, "password": password,
                "options": {"email_redirect_to": "https://taskking.vercel.app/login"}
            })
            new_user_id = res.user.id
            
            # Generate Unique Code
            import random, string
            chars = string.ascii_uppercase + string.digits
            my_unique_code = 'TK' + ''.join(random.choices(chars, k=4))
            
            supabase.table('profiles').update({
                'full_name': full_name,
                'mobile_number': mobile_number,
                'referral_code': my_unique_code,
                'balance': 0.00
            }).eq('id', new_user_id).execute()

            # Referral Bonus Logic
            if used_ref_code:
                try:
                    referrer_res = supabase.table('profiles').select('*').eq('referral_code', used_ref_code).single().execute()
                    referrer = referrer_res.data
                    if referrer:
                        supabase.table('profiles').update({'referred_by': referrer['id']}).eq('id', new_user_id).execute()
                        # Bonus
                        supabase.table('profiles').update({'balance': float(referrer['balance']) + 10.00}).eq('id', referrer['id']).execute()
                        supabase.table('profiles').update({'balance': 10.00}).eq('id', new_user_id).execute()
                except: pass

            flash("✅ একাউন্ট তৈরি হয়েছে! ইমেইল ভেরিফাই করে লগিন করুন।", "info")
            return redirect(url_for('login'))
            
        except Exception as e:
            flash("❌ রেজিস্ট্রেশন ব্যর্থ হয়েছে।", "error")
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear() # শুধু লগআউট হবে, কিন্তু কুকি থেকে যাবে
    return redirect(url_for('login'))

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    # ফিল্টার প্যারামিটার
    search = request.args.get('q')
    sort_by = request.args.get('sort', 'newest') # default newest
    filter_status = request.args.get('status', 'all')

    # ১. বেসিক কুয়েরি
    query = supabase.table('profiles').select('*')

    # ২. সার্চ লজিক
    if search:
        query = query.ilike('email', f'%{search}%')

    # ৩. স্ট্যাটাস ফিল্টার
    if filter_status == 'banned':
        query = query.eq('is_banned', True)
    elif filter_status == 'active':
        query = query.eq('is_active', True)
    elif filter_status == 'unpaid':
        query = query.eq('is_active', False)

    # ৪. সর্টিং লজিক
    if sort_by == 'balance_high':
        query = query.order('balance', desc=True)
    elif sort_by == 'balance_low':
        query = query.order('balance', desc=False)
    elif sort_by == 'oldest':
        query = query.order('created_at', desc=False)
    else: # newest
        query = query.order('created_at', desc=True)

    try:
        users = query.execute().data
        
        # ৫. স্ট্যাটাস কাউন্ট (Dashboard Stats)
        total_users = len(users)
        total_balance = sum(float(u['balance']) for u in users)
        banned_users = sum(1 for u in users if u.get('is_banned'))
        active_users = sum(1 for u in users if u.get('is_active'))

        # ৬. রেফারেল কাউন্ট যুক্ত করা
        for u in users:
            try:
                count_res = supabase.table('profiles').select('id', count='exact', head=True).eq('referred_by', u['id']).execute()
                u['ref_count'] = count_res.count
            except:
                u['ref_count'] = 0
                
    except Exception as e:
        print(f"User Fetch Error: {e}")
        users = []
        total_users = 0
        total_balance = 0
        banned_users = 0
        active_users = 0

    return render_template('users.html', 
                           users=users, 
                           stats={
                               'total': total_users,
                               'balance': round(total_balance, 2),
                               'banned': banned_users,
                               'active': active_users
                           },
                           filters={'q': search, 'sort': sort_by, 'status': filter_status})
    
# --- ADMIN: BAN / UNBAN USER ---
@app.route('/admin/user/ban/<string:user_id>')
@login_required
@admin_required
def ban_user(user_id):
    try:
        # ১. ডাটাবেস থেকে বর্তমান স্ট্যাটাস জানা
        user_res = supabase.table('profiles').select('is_banned').eq('id', user_id).single().execute()
        
        if not user_res.data:
            flash("ইউজার খুঁজে পাওয়া যায়নি!", "error")
            return redirect(url_for('admin_users'))

        # ২. স্ট্যাটাস উল্টে দেওয়া (Toggle: True হলে False, False হলে True)
        current_status = user_res.data.get('is_banned', False)
        new_status = not current_status
        
        # ৩. ডাটাবেসে আপডেট করা
        supabase.table('profiles').update({
            'is_banned': new_status
        }).eq('id', user_id).execute()
        
        # ৪. কনফার্মেশন মেসেজ
        if new_status:
            flash("⛔ ইউজারকে সফলভাবে ব্যান করা হয়েছে!", "error") # লাল মেসেজ
        else:
            flash("✅ ইউজার আনব্যান (Active) হয়েছে!", "success") # সবুজ মেসেজ
        
    except Exception as e:
        print(f"Ban Error: {e}")
        flash(f"Action Failed: {str(e)}", "error")
        
    return redirect(url_for('admin_users'))

# 3. Delete User Profile
# --- ADMIN: DELETE USER (FIXED FOREIGN KEY ERROR) ---
@app.route('/admin/user/delete/<string:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    try:
        # ১. এই ইউজার যাদের রেফার করেছিল, তাদের 'referred_by' খালি করে দেওয়া
        # যাতে ডাটাবেস এরর না দেয়
        supabase.table('profiles').update({
            'referred_by': None
        }).eq('referred_by', user_id).execute()

        # ২. এই ইউজারের অন্যান্য সব ডাটা মুছে ফেলা (Clean Up)
        supabase.table('withdrawals').delete().eq('user_id', user_id).execute()
        supabase.table('submissions').delete().eq('user_id', user_id).execute()
        supabase.table('activation_requests').delete().eq('user_id', user_id).execute()
        
        # ৩. সবশেষে মেইন প্রোফাইল ডিলিট করা
        supabase.table('profiles').delete().eq('id', user_id).execute()
        
        flash("🗑️ ইউজার এবং তার সকল তথ্য সফলভাবে মুছে ফেলা হয়েছে।", "success")
        
    except Exception as e:
        print(f"Delete Error: {e}") # কনসোলে এরর প্রিন্ট করবে
        flash(f"Delete Failed: {str(e)}", "error")
        
    return redirect(url_for('admin_users'))
# 4. Update Balance
@app.route('/admin/user/balance', methods=['POST'])
@login_required
@admin_required
def update_user_balance():
    user_id = request.form.get('user_id')
    new_balance = request.form.get('amount')
    
    try:
        supabase.table('profiles').update({
            'balance': float(new_balance)
        }).eq('id', user_id).execute()
        
        flash("💰 ব্যালেন্স আপডেট করা হয়েছে!", "success")
    except Exception as e:
        flash("Update Failed", "error")
        
    return redirect(url_for('admin_users'))
# --- USER DASHBOARD ROUTE (FULL LOGIC) ---
@app.route('/dashboard')
@login_required
def dashboard():
    from datetime import datetime
    import random

    # ১. আজকের তারিখ বের করা (UTC)
    # এটি Daily Check-in বাটন Disable করার জন্য এবং Today's Income বের করতে লাগবে
    today_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    today_income = 0.0
    pending_income = 0.0
    leaderboard = []
    
    # ২. ইনকাম স্ট্যাটাস ক্যালকুলেশন (Real-time)
    try:
        # ইউজারের সব সাবমিশন এবং টাস্ক ডাটা আনা
        subs = supabase.table('submissions').select('*').eq('user_id', session['user_id']).execute().data
        all_tasks = supabase.table('tasks').select('id, reward').execute().data
        
        # টাস্কের রিওওার্ড ম্যাপ করা {task_id: reward} - ফাস্ট প্রসেসিং এর জন্য
        task_map = {t['id']: float(t['reward']) for t in all_tasks}
        
        for sub in subs:
            reward = task_map.get(sub['task_id'], 0.0)
            
            # Pending Income হিসাব
            if sub['status'] == 'pending':
                pending_income += reward
            
            # Today's Income হিসাব (Approved হতে হবে এবং আজকের তারিখের হতে হবে)
            # Supabase timestamp example: '2025-01-01T12:00:00+00:00' -> split('T')[0] gives date
            sub_date_str = sub['created_at'].split('T')[0]
            
            if sub['status'] == 'approved' and sub_date_str == today_date:
                today_income += reward
                
    except Exception as e:
        print(f"Dashboard Stats Error: {e}")

    # ৩. টপ আর্নার লিডারবোর্ড (প্রতিদিন চেঞ্জ হবে)
    try:
        # ডাটাবেস থেকে সবচেয়ে বেশি ব্যালেন্স ওয়ালা ২০ জন ইউজারকে আনা
        top_users = supabase.table('profiles').select('email, balance').order('balance', desc=True).limit(20).execute().data
        
        if top_users:
            # আজকের তারিখ অনুযায়ী র‍্যান্ডম সিড সেট করা
            # এর ফলে আজ সারাদিন একই ৩ জন টপ লিস্টে থাকবে
            random.seed(today_date)
            
            # টপ ২০ জন থেকে র‍্যান্ডম ৩ জনকে বেছে নেওয়া
            leaderboard = random.sample(top_users, k=min(3, len(top_users)))
            
            # র‍্যান্ডম আবার নরমাল করা (যাতে অন্য ফাংশনে প্রভাব না পড়ে)
            random.seed()
            
    except Exception as e:
        print(f"Leaderboard Error: {e}")

    # ৪. টেমপ্লেটে ডাটা পাঠানো
    return render_template('index.html', 
                           user=g.user, 
                           settings=g.settings, 
                           today_income=round(today_income, 2),
                           pending_income=round(pending_income, 2),
                           leaderboard=leaderboard,
                           today_date=today_date)

@app.route('/tasks')
@login_required
def tasks():
    try:
        # ১. সব অ্যাক্টিভ টাস্ক আনা
        all_tasks = supabase.table('tasks').select('*').eq('is_active', True).order('id', desc=True).execute().data
        
        # ২. ইউজারের সাধারণ টাস্কের সাবমিশন আনা
        subs = supabase.table('submissions').select('task_id, status').eq('user_id', session['user_id']).execute().data
        
        # সাবমিশন স্ট্যাটাস ম্যাপ করা
        task_status_map = {}
        for s in subs:
            tid = s['task_id']
            st = s['status']
            # যদি একাধিক সাবমিশন থাকে, pending/approved কে প্রাধান্য দেওয়া
            if tid not in task_status_map or st in ['pending', 'approved']:
                task_status_map[tid] = st

        # ৩. ফিল্টারিং লজিক (Pending/Approved হলে হাইড, Rejected বা নতুন হলে শো করবে)
        available_tasks = []
        for t in all_tasks:
            tid = t['id']
            status = task_status_map.get(tid)
            
            if status in ['pending', 'approved']:
                continue # হাইড করো
            
            # যদি রিজেক্টেড হয়, তবে একটি ফ্ল্যাগ সেট করো
            t['is_rejected'] = (status == 'rejected')
            available_tasks.append(t)

        # ৪. স্পেশাল টাস্ক স্ট্যাটাস চেক করা
        spec_subs = supabase.table('special_submissions').select('status').eq('user_id', session['user_id']).execute().data
        show_special = True
        special_rejected = False
        
        if spec_subs:
            for s in spec_subs:
                if s['status'] in ['pending', 'approved']:
                    show_special = False # হাইড করো
                    break
                elif s['status'] == 'rejected':
                    special_rejected = True

    except Exception as e:
        print(f"Task Error: {e}")
        available_tasks =[]
        show_special = False
        special_rejected = False

    return render_template('tasks.html', 
                           tasks=available_tasks, 
                           show_special=show_special, 
                           special_rejected=special_rejected,
                           special_task=SPECIAL_TASK_INFO,
                           user=g.user)
    
# --- 2. NEW HISTORY ROUTE (Task & Withdraw) ---
@app.route('/history')
@login_required
def history():
    # A. কাজের হিস্টোরি (Task Submissions)
    try:
        subs_res = supabase.table('submissions').select('*').eq('user_id', session['user_id']).order('created_at', desc=True).execute()
        my_tasks = subs_res.data
        
        # টাস্কের নাম (Title) যুক্ত করা (যেহেতু submissions টেবিলে শুধু ID আছে)
        for item in my_tasks:
            try:
                task_info = supabase.table('tasks').select('title, reward').eq('id', item['task_id']).single().execute()
                item['title'] = task_info.data['title']
                item['reward'] = task_info.data['reward']
            except:
                item['title'] = "Unknown Task" # যদি টাস্ক ডিলিট হয়ে যায়
                item['reward'] = 0
    except:
        my_tasks = []

    # B. উইথড্রয়াল হিস্টোরি (Withdrawals)
    try:
        with_res = supabase.table('withdrawals').select('*').eq('user_id', session['user_id']).order('created_at', desc=True).execute()
        my_withdrawals = with_res.data
    except:
        my_withdrawals = []

    return render_template('history.html', tasks=my_tasks, withdrawals=my_withdrawals, user=g.user)
# --- USER: ACTIVATION PAGE & STATUS CHECK ---
@app.route('/activate')
@login_required
def activate_account():
    # ১. যদি ইউজার ইতিমধ্যে এক্টিভ থাকে, ড্যাশবোর্ডে পাঠাও
    if g.user.get('is_active'):
        flash("✅ আপনার একাউন্ট ইতিমধ্যে ভেরিফাইড!", "success")
        return redirect(url_for('dashboard'))

    # ২. চেক করা ইউজার আগে কোনো রিকোয়েস্ট পাঠিয়েছে কিনা
    try:
        req_res = supabase.table('activation_requests').select('*').eq('user_id', session['user_id']).order('created_at', desc=True).limit(1).execute()
        existing_request = req_res.data[0] if req_res.data else None
    except:
        existing_request = None

    return render_template('activation.html', user=g.user, request_data=existing_request)


# --- USER: SUBMIT REQUEST (ONLY ONCE) ---
@app.route('/activate/submit', methods=['POST'])
@login_required
def submit_activation():
    # ১. আবার চেক করা ইউজার অলরেডি সাবমিট করেছে কিনা (ডাবল সাবমিশন রোধ)
    try:
        check_res = supabase.table('activation_requests').select('*').eq('user_id', session['user_id']).eq('status', 'pending').execute()
        if check_res.data:
            flash("⚠️ আপনার একটি রিকোয়েস্ট ইতিমধ্যে পেন্ডিং আছে। অপেক্ষা করুন।", "warning")
            return redirect(url_for('activate_account'))
    except:
        pass

    # ২. ফর্ম ডাটা নেওয়া
    method = request.form.get('method')
    sender_number = request.form.get('sender_number')
    trx_id = request.form.get('trx_id')
    
    try:
        # ৩. ডাটাবেসে সেভ করা
        supabase.table('activation_requests').insert({
            'user_id': session['user_id'],
            'method': method,
            'sender_number': sender_number,
            'trx_id': trx_id,
            'status': 'pending'
        }).execute()
        
        flash("✅ তথ্য জমা হয়েছে! এডমিন শীঘ্রই যাচাই করবেন।", "success")
        
    except Exception as e:
        print(f"Activation Error: {e}")
        flash("❌ ডাটা সেভ হয়নি। আবার চেষ্টা করুন।", "error")
        
    return redirect(url_for('activate_account'))
    
# --- ADMIN: APPROVE / REJECT ACTIVATION ---
@app.route('/admin/activation/<action>/<int:req_id>')
@login_required
@admin_required
def activation_action(action, req_id):
    try:
        # ১. রিকোয়েস্ট ডিটেইলস আনা
        req_res = supabase.table('activation_requests').select('*').eq('id', req_id).single().execute()
        req_data = req_res.data
        
        if not req_data:
            flash("রিকোয়েস্ট পাওয়া যায়নি!", "error")
            return redirect(url_for('admin_activations'))

        # ২. যদি APPROVE করা হয়
        if action == 'approve':
            # A. ইউজারকে Active করা (Main Job)
            supabase.table('profiles').update({
                'is_active': True
            }).eq('id', req_data['user_id']).execute()
            
            # B. রিকোয়েস্ট স্ট্যাটাস আপডেট
            supabase.table('activation_requests').update({
                'status': 'approved'
            }).eq('id', req_id).execute()
            
            flash(f"✅ ইউজার সফলভাবে অ্যাক্টিভ হয়েছে!", "success")

        # ৩. যদি REJECT করা হয়
        elif action == 'reject':
            supabase.table('activation_requests').update({
                'status': 'rejected'
            }).eq('id', req_id).execute()
            flash("❌ রিকোয়েস্ট বাতিল করা হয়েছে।", "error")

    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        
    return redirect(url_for('admin_activations'))


# --- ADMIN: VIEW ACTIVATION REQUESTS ---
@app.route('/admin/activations')
@login_required
@admin_required
def admin_activations():
    # ১. পেন্ডিং রিকোয়েস্ট আনা
    req_res = supabase.table('activation_requests').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
    requests_data = req_res.data
    
    # ২. ইউজার ইমেইল যুক্ত করা
    final_data = []
    for req in requests_data:
        try:
            user = supabase.table('profiles').select('email').eq('id', req['user_id']).single().execute().data
            req['user_email'] = user['email']
            final_data.append(req)
        except:
            continue

    return render_template('activations.html', requests=final_data)

# --- USER: INCOME SUMMARY PAGE ---
@app.route('/income')
@login_required
def income_summary():
    from datetime import datetime
    today_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    # 1. Balances
    main_bal = float(g.user.get('balance', 0.0))
    vip_bal = float(g.user.get('vip_balance', 0.0))
    
    # 2. Total Withdraw (Only Approved)
    try:
        with_res = supabase.table('withdrawals').select('amount').eq('user_id', session['user_id']).eq('status', 'approved').execute().data
        total_withdraw = sum(float(w['amount']) for w in with_res)
    except:
        total_withdraw = 0.0
        
    # 3. Referrals Count
    try:
        ref_res = supabase.table('profiles').select('id').eq('referred_by', session['user_id']).execute().data
        ref_count = len(ref_res)
    except:
        ref_count = 0
        
    # 4. Today's Income & Pending Income
    today_income = 0.0
    pending_income = 0.0
    try:
        # Normal Tasks
        subs = supabase.table('submissions').select('*').eq('user_id', session['user_id']).execute().data
        all_tasks = supabase.table('tasks').select('id, reward').execute().data
        task_map = {t['id']: float(t['reward']) for t in all_tasks}
        
        for sub in subs:
            reward = task_map.get(sub['task_id'], 0.0)
            if sub['status'] == 'pending':
                pending_income += reward
            elif sub['status'] == 'approved' and sub['created_at'].split('T')[0] == today_date:
                today_income += reward
                
        # Special Tasks (if any pending/approved today)
        specs = supabase.table('special_submissions').select('*').eq('user_id', session['user_id']).execute().data
        spec_reward = SPECIAL_TASK_INFO['reward']
        for sp in specs:
            if sp['status'] == 'pending':
                pending_income += spec_reward
            elif sp['status'] == 'approved' and sp['created_at'].split('T')[0] == today_date:
                today_income += spec_reward
                
    except Exception as e:
        print(f"Income Calc Error: {e}")

    return render_template('income.html', 
                           user=g.user,
                           main_bal=main_bal,
                           vip_bal=vip_bal,
                           total_withdraw=total_withdraw,
                           ref_count=ref_count,
                           today_income=today_income,
                           pending_income=pending_income)
    
# -------------------------------------------------------------------
# 5. ADMIN PANEL
# -------------------------------------------------------------------
@app.route('/admin', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_panel():
    if request.method == 'POST':
        m_mode = True if request.form.get('maintenance') == 'on' else False
        a_req = True if request.form.get('activation') == 'on' else False
        notice = request.form.get('notice')

        try:
            supabase.table('site_settings').update({
                'maintenance_mode': m_mode,
                'activation_required': a_req,
                'notice_text': notice
            }).eq('id', 1).execute()

            flash("✅ সেটিংস সফলভাবে সেভ হয়েছে!", "success")
            return redirect(url_for('admin_panel'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    try:
        user_count = supabase.table('profiles').select('*', count='exact').execute().count
    except:
        user_count = 0

    return render_template('admin.html', user=g.user, settings=g.settings, user_count=user_count)

if __name__ == '__main__':
    app.run(debug=True)
