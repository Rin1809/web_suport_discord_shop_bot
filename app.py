import os
import json
import psycopg2
import requests
import math
import re
import time
from psycopg2.extras import Json, RealDictCursor
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO
from collections import defaultdict

# load db functions tu du an bot
import sys
# them duong dan den thu muc cha de import module database
# can than voi cach trien khai thuc te
try:
    bot_project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Discord_Role_Shop'))
    if bot_project_path not in sys.path:
        sys.path.insert(0, bot_project_path)
    from database import database as db
except ImportError:
    print("WARNING: Khong the import module database tu project bot. Su dung ket noi truc tiep.")
    db = None


load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = "https://discord.com/api/v10"

# khoi tao db neu co the
if db:
    db.init_db(DATABASE_URL)

# cache
_user_cache = {}
_guild_members_cache = {}
CACHE_DURATION_SECONDS = 300 # 5 phut

def discord_api_request(endpoint, method='GET', payload=None):
    if not BOT_TOKEN:
        return None
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        if method == 'GET':
            res = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)
        elif method == 'POST':
            res = requests.post(f"{API_BASE_URL}{endpoint}", headers=headers, json=payload)
        elif method == 'PATCH':
            res = requests.patch(f"{API_BASE_URL}{endpoint}", headers=headers, json=payload)
        elif method == 'DELETE':
            res = requests.delete(f"{API_BASE_URL}{endpoint}", headers=headers)
        
        res.raise_for_status()
        return res.json() if res.status_code != 204 else None
    except requests.RequestException as e:
        print(f"Loi goi API Discord toi {endpoint}: {e}")
        if 'res' in locals() and res is not None:
             print(f"Response body: {res.text}")
        return None

def get_user_info(user_id):
    user_id_str = str(user_id)
    if not user_id_str or not user_id_str.isdigit():
        return {'id': user_id_str, 'name': 'N/A', 'avatar_url': "https://cdn.discordapp.com/embed/avatars/0.png"}

    if user_id_str in _user_cache:
        return _user_cache[user_id_str]
    
    user_data = discord_api_request(f"/users/{user_id_str}")
    if user_data:
        avatar_hash = user_data.get('avatar')
        info = {
            'id': user_id_str,
            'name': user_data.get('global_name') or user_data.get('username', f'Unknown User {user_id_str}'),
            'avatar_url': f"https://cdn.discordapp.com/avatars/{user_id_str}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
        }
        _user_cache[user_id_str] = info
        return info
    return {
        'id': user_id_str,
        'name': f'Unknown User {user_id_str}',
        'avatar_url': "https://cdn.discordapp.com/embed/avatars/0.png"
    }


def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Loi ket noi database: {e}")
        return None

def parse_form_data(form):
    config = defaultdict(dict)
    
    simple_keys = [
        'shop_channel_id', 'leaderboard_thread_id', 'ADMIN_LOG_CHANNEL_ID',
        'EMBED_COLOR', 'SELL_REFUND_PERCENTAGE',
        'SHOP_EMBED_THUMBNAIL_URL', 'SHOP_EMBED_IMAGE_URL',
        'EARNING_RATES_IMAGE_URL', 'SHOP_DISPLAY_STYLE'
    ]
    for key in simple_keys:
        if form.get(key):
            config[key] = form.get(key)
    
    ping_role_ids = request.form.getlist('CUSTOM_ROLE_PING_ROLES[]')
    if ping_role_ids:
        config['CUSTOM_ROLE_PING_ROLES'] = [int(rid) for rid in ping_role_ids]
    else:
        config['CUSTOM_ROLE_PING_ROLES'] = []

    for key, value in form.items():
        if key.endswith('[]'):
            continue
        if '[' in key and ']' in key:
            parts = key.replace(']', '').split('[')
            d = config
            for part in parts[:-1]:
                if part not in d:
                    d[part] = defaultdict(dict)
                d = d[part]
            d[parts[-1]] = value if value else None

    if config.get('shop_channel_id'):
        config['shop_channel_id'] = int(config['shop_channel_id'])
    else:
         config['shop_channel_id'] = None

    if config.get('ADMIN_LOG_CHANNEL_ID'):
        config['ADMIN_LOG_CHANNEL_ID'] = int(config['ADMIN_LOG_CHANNEL_ID'])
    else:
        config['ADMIN_LOG_CHANNEL_ID'] = None

    if config.get('leaderboard_thread_id'):
        config['leaderboard_thread_id'] = int(config['leaderboard_thread_id'])
    else:
        config['leaderboard_thread_id'] = None

    if 'CURRENCY_RATES' in config and 'default' in config['CURRENCY_RATES']:
        default_rates = config['CURRENCY_RATES']['default']
        if default_rates.get('MESSAGES_PER_COIN'):
            default_rates['MESSAGES_PER_COIN'] = int(default_rates['MESSAGES_PER_COIN'])
        if default_rates.get('REACTIONS_PER_COIN'):
            default_rates['REACTIONS_PER_COIN'] = int(default_rates['REACTIONS_PER_COIN'])

    if 'CUSTOM_ROLE_CONFIG' in config:
        custom_role_conf = config['CUSTOM_ROLE_CONFIG']
        if custom_role_conf.get('MIN_BOOST_COUNT'):
            custom_role_conf['MIN_BOOST_COUNT'] = int(custom_role_conf['MIN_BOOST_COUNT'])
        if custom_role_conf.get('PRICE'):
            custom_role_conf['PRICE'] = int(custom_role_conf['PRICE'])
        if custom_role_conf.get('DEFAULT_PURCHASE_PRICE'):
            custom_role_conf['DEFAULT_PURCHASE_PRICE'] = int(custom_role_conf['DEFAULT_PURCHASE_PRICE'])

    if 'REGULAR_USER_ROLE_CREATION' in config:
        regular_conf = config['REGULAR_USER_ROLE_CREATION']
        regular_conf['ENABLED'] = regular_conf.get('ENABLED') == 'true'
        if regular_conf.get('CREATION_PRICE'):
            regular_conf['CREATION_PRICE'] = int(regular_conf['CREATION_PRICE'])
        if regular_conf.get('SHOP_PRICE_MULTIPLIER'):
            regular_conf['SHOP_PRICE_MULTIPLIER'] = float(regular_conf['SHOP_PRICE_MULTIPLIER'])

    if config.get('SELL_REFUND_PERCENTAGE'):
        config['SELL_REFUND_PERCENTAGE'] = float(config['SELL_REFUND_PERCENTAGE'])

    if 'BOOSTER_MULTIPLIER_CONFIG' in config:
        booster_conf = config['BOOSTER_MULTIPLIER_CONFIG']
        booster_conf['ENABLED'] = booster_conf.get('ENABLED') == 'true'
        if booster_conf.get('BASE_MULTIPLIER'):
            booster_conf['BASE_MULTIPLIER'] = float(booster_conf['BASE_MULTIPLIER'])
        if booster_conf.get('PER_BOOST_ADDITION'):
            booster_conf['PER_BOOST_ADDITION'] = float(booster_conf['PER_BOOST_ADDITION'])

    cat_ids = request.form.getlist('category_rate_id[]')
    cat_msgs = request.form.getlist('category_rate_messages[]')
    cat_reacts = request.form.getlist('category_rate_reactions[]')
    
    config['CURRENCY_RATES']['categories'] = {}
    for i, cat_id in enumerate(cat_ids):
        if cat_id:
            config['CURRENCY_RATES']['categories'][cat_id] = {
                "MESSAGES_PER_COIN": int(cat_msgs[i]) if cat_msgs[i] else None,
                "REACTIONS_PER_COIN": int(cat_reacts[i]) if cat_reacts[i] else None
            }
    
    chan_ids = request.form.getlist('channel_rate_id[]')
    chan_msgs = request.form.getlist('channel_rate_messages[]')
    chan_reacts = request.form.getlist('channel_rate_reactions[]')

    config['CURRENCY_RATES']['channels'] = {}
    for i, chan_id in enumerate(chan_ids):
        if chan_id:
            config['CURRENCY_RATES']['channels'][chan_id] = {
                "MESSAGES_PER_COIN": int(chan_msgs[i]) if chan_msgs[i] else None,
                "REACTIONS_PER_COIN": int(chan_reacts[i]) if chan_reacts[i] else None
            }

    qna_labels = request.form.getlist('qna_label[]')
    qna_descriptions = request.form.getlist('qna_description[]')
    qna_emojis = request.form.getlist('qna_emoji[]')
    qna_titles = request.form.getlist('qna_answer_title[]')
    qna_descs = request.form.getlist('qna_answer_description[]')
    
    config['QNA_DATA'] = []
    for i, label in enumerate(qna_labels):
        if label:
            config['QNA_DATA'].append({
                "label": label,
                "description": qna_descriptions[i],
                "emoji": qna_emojis[i],
                "answer_title": qna_titles[i],
                "answer_description": qna_descs[i]
            })

    return json.loads(json.dumps(config))


@app.route('/')
def index():
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return render_template('index.html', guilds=[])
        
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT guild_id FROM guild_configs ORDER BY guild_id;")
        guilds_data = cur.fetchall()
    conn.close()
    
    guilds_details = []
    for row in guilds_data:
        guild_id = row['guild_id']
        guild_info = discord_api_request(f"/guilds/{guild_id}")
        if guild_info:
            icon_hash = guild_info.get('icon')
            icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png" if icon_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
            guilds_details.append({
                'id': guild_id,
                'name': guild_info.get('name', f'Unknown Server {guild_id}'),
                'icon_url': icon_url
            })
        else:
            guilds_details.append({
                'id': guild_id,
                'name': f'Server ID: {guild_id} (Không thể lấy thông tin)',
                'icon_url': "https://cdn.discordapp.com/embed/avatars/0.png"
            })
    
    return render_template('index.html', guilds=guilds_details)


@app.route('/edit/<int:guild_id>', methods=['GET', 'POST'])
def edit_config(guild_id):
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        config_data_json = parse_form_data(request.form)

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE guild_configs SET config_data = %s WHERE guild_id = %s;",
                    (Json(config_data_json), guild_id)
                )
                
                form_role_ids = request.form.getlist('shop_role_id[]')
                form_role_names = request.form.getlist('shop_role_name[]')
                form_role_prices = request.form.getlist('shop_role_price[]')
                form_role_colors = request.form.getlist('shop_role_color[]')
                form_role_creators = request.form.getlist('shop_role_creator_id[]')

                cur.execute("SELECT role_id FROM shop_roles WHERE guild_id = %s", (guild_id,))
        
                db_role_ids = {row['role_id'] for row in cur.fetchall()}

                form_role_ids = request.form.getlist('shop_role_id[]')
                valid_form_role_ids = {int(rid) for rid in form_role_ids if rid}

                roles_to_delete = db_role_ids - valid_form_role_ids

                if roles_to_delete:
                    for del_id in roles_to_delete:
                        discord_api_request(f"/guilds/{guild_id}/roles/{del_id}", method='DELETE')
                    
                    cur.execute("DELETE FROM shop_roles WHERE guild_id = %s AND role_id = ANY(%s)", (guild_id, list(roles_to_delete)))


                for i, role_name in enumerate(form_role_names):
                    role_name = role_name.strip()
                    if not (role_name and form_role_prices[i]):
                        continue
                    
                    price = int(form_role_prices[i])
                    creator_id = int(form_role_creators[i]) if form_role_creators[i] else None
                    hex_color = (form_role_colors[i] or '#99aab5').lstrip('#')
                    color_int = int(hex_color, 16)
                    
                    role_id = form_role_ids[i] if form_role_ids[i] else None

                    if role_id:
                        # check role nay co phai role shop ko
                        cur.execute("SELECT 1 FROM shop_roles WHERE role_id = %s AND guild_id = %s", (int(role_id), guild_id))
                        if cur.fetchone() is None:
                            flash(f"Lỗi bảo mật: Đã cố gắng chỉnh sửa role ID {role_id} không thuộc shop.", "danger")
                            continue
                        
                        payload = {'name': role_name, 'color': color_int}
                        discord_api_request(f"/guilds/{guild_id}/roles/{role_id}", method='PATCH', payload=payload)
                    else:
                        payload = {'name': role_name, 'color': color_int}
                        created_role = discord_api_request(f"/guilds/{guild_id}/roles", method='POST', payload=payload)
                        if created_role:
                            role_id = created_role['id']
                        else:
                            flash(f"Không thể tạo role '{role_name}'.", "danger")
                            continue
                    
                    if role_id:
                        cur.execute(
                            """
                            INSERT INTO shop_roles (guild_id, role_id, price, creator_id) VALUES (%s, %s, %s, %s)
                            ON CONFLICT (role_id) DO UPDATE SET price = EXCLUDED.price
                            """,
                            (guild_id, int(role_id), price, creator_id)
                        )

            conn.commit()
            flash(f"Đã cập nhật thành công cấu hình cho Server ID: {guild_id}", "success")
            # gui event reload cho bot
            socketio.emit('config_updated', {'guild_id': str(guild_id)})
        except Exception as e:
            conn.rollback()
            flash(f"Lỗi khi cập nhật database: {e}", "danger")
        finally:
            conn.close()
        
        return redirect(url_for('edit_config', guild_id=guild_id))

    # GET
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT config_data FROM guild_configs WHERE guild_id = %s;", (guild_id,))
        db_result = cur.fetchone()

        cur.execute("SELECT role_id, price, creator_id FROM shop_roles WHERE guild_id = %s ORDER BY price ASC", (guild_id,))
        shop_roles_db = cur.fetchall()

    conn.close()

    if not db_result:
        flash(f"Không tìm thấy cấu hình cho Server ID: {guild_id}", "warning")
        return redirect(url_for('index'))
    
    config = db_result['config_data'] or {}

    keys_to_ensure = {
        "MESSAGES": {}, "FOOTER_MESSAGES": {}, 
        "CURRENCY_RATES": {"default": {}, "categories": {}, "channels": {}},
        "CUSTOM_ROLE_CONFIG": {}, "QNA_DATA": [],
        "BOOSTER_MULTIPLIER_CONFIG": {},
        "REGULAR_USER_ROLE_CREATION": {},
        "CUSTOM_ROLE_PING_ROLES": []
    }
    for key, default_value in keys_to_ensure.items():
        if key not in config:
            config[key] = default_value
    
    guild_details = discord_api_request(f"/guilds/{guild_id}")
    if guild_details:
        icon_hash = guild_details.get('icon')
        guild_details['icon_url'] = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png" if icon_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
    
    all_channels = discord_api_request(f"/guilds/{guild_id}/channels")
    all_roles_raw = discord_api_request(f"/guilds/{guild_id}/roles")
    
    text_channels, category_channels, rateable_channels = [], [], []
    if all_channels:
        text_channels = [ch for ch in all_channels if ch['type'] == 0]
        category_channels = [ch for ch in all_channels if ch['type'] == 4]
        rateable_channels = [ch for ch in all_channels if ch['type'] in [0, 5, 15]]
    
    creator_ids = {r['creator_id'] for r in shop_roles_db if r['creator_id']}
    user_details = {str(uid): get_user_info(uid) for uid in creator_ids}

    role_id_to_details_map = {str(r['id']): {'name': r['name'], 'color': f"#{r['color']:06x}" if r['color'] != 0 else '#000000'} for r in all_roles_raw} if all_roles_raw else {}
    shop_roles_with_details = []
    for r in shop_roles_db:
        details = role_id_to_details_map.get(str(r['role_id']))
        if details:
            shop_roles_with_details.append({
                'id': r['role_id'],
                'name': details['name'],
                'color': details['color'],
                'price': r['price'],
                'creator_id': r['creator_id']
            })

    # lay ds custom role
    custom_roles_db = db.get_all_custom_roles_for_guild(guild_id) if db else []
    custom_roles_details = []
    if custom_roles_db and all_roles_raw:
        # tao map de tra cuu nhanh
        role_info_map = {str(r['id']): r for r in all_roles_raw}
        for cr in custom_roles_db:
            role_info = role_info_map.get(str(cr['role_id']))
            if role_info:
                custom_roles_details.append({
                    'user_info': get_user_info(cr['user_id']),
                    'role_info': {
                        'id': role_info['id'],
                        'name': role_info['name'],
                        'color': f"#{role_info['color']:06x}"
                    }
                })


    return render_template(
        'edit_config.html', 
        guild_id=guild_id, 
        config=config, 
        guild=guild_details,
        text_channels=text_channels,
        category_channels=category_channels,
        rateable_channels=rateable_channels,
        shop_roles=shop_roles_with_details,
        all_roles=all_roles_raw or [],
        user_details=user_details,
        custom_roles_details=custom_roles_details # truyen vao template
    )

@app.route('/wipe/<int:guild_id>', methods=['POST'])
def wipe_server_data(guild_id):
    if not db:
        flash("Chức năng database không khả dụng.", "danger")
        return redirect(url_for('edit_config', guild_id=guild_id))
        
    try:
        # 1. Xoa du lieu db va lay ve ID role can xoa tren Discord
        role_ids_to_delete = db.wipe_guild_data(guild_id)
        
        # 2. Xoa role tren Discord
        deleted_count = 0
        for role_id in role_ids_to_delete:
            try:
                # ly do de log
                reason = "Server data wipe from dashboard"
                discord_api_request(f"/guilds/{guild_id}/roles/{role_id}?reason={reason}", method='DELETE')
                deleted_count += 1
            except Exception as e:
                print(f"Khong the xoa role {role_id} cua guild {guild_id}: {e}")
        
        flash(f"Đã xóa thành công toàn bộ dữ liệu của server {guild_id}. {deleted_count} role đã bị xóa khỏi Discord.", "success")

    except Exception as e:
        flash(f"Đã xảy ra lỗi nghiêm trọng khi xóa dữ liệu server: {e}", "danger")
    
    return redirect(url_for('edit_config', guild_id=guild_id))


@app.route('/edit/<int:guild_id>/members')
def members(guild_id):
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return redirect(url_for('edit_config', guild_id=guild_id))

    guild_details = discord_api_request(f"/guilds/{guild_id}")
    if not guild_details:
        flash(f"Không thể lấy thông tin server {guild_id}", "danger")
        return redirect(url_for('index'))
    
    guild_id_str = str(guild_id)
    now = time.time()
    api_members = []
    
    if guild_id_str in _guild_members_cache and (now - _guild_members_cache[guild_id_str]['timestamp'] < CACHE_DURATION_SECONDS):
        api_members = _guild_members_cache[guild_id_str]['data']
    else:
        fetched_members = discord_api_request(f"/guilds/{guild_id}/members?limit=1000")
        if fetched_members is not None:
            api_members = fetched_members
            _guild_members_cache[guild_id_str] = {'data': api_members, 'timestamp': now}
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT user_id, balance FROM users WHERE guild_id = %s", (guild_id,))
        db_users_list = cur.fetchall()
    conn.close()
    
    db_users_map = {str(u['user_id']): u for u in db_users_list}

    search_query = request.args.get('search', '').strip().lower()
    if search_query:
        filtered_members = []
        for member in api_members:
            user_info = member.get('user', {})
            display_name = (user_info.get('global_name') or user_info.get('username', '')).lower()
            if search_query in display_name:
                filtered_members.append(member)
        api_members = filtered_members
    
    members_data = []
    for member in api_members:
        user = member.get('user', {})
        user_id_str = user.get('id')
        if not user_id_str or user.get('bot'):
            continue
            
        avatar_hash = user.get('avatar')
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id_str}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        db_info = db_users_map.get(user_id_str, {})

        members_data.append({
            'id': user_id_str,
            'name': user.get('global_name') or user.get('username'),
            'discriminator': user.get('discriminator'),
            'avatar_url': avatar_url,
            'balance': db_info.get('balance', 0)
        })

    page = request.args.get('page', 1, type=int)
    per_page = 24 
    total_members = len(members_data)
    total_pages = math.ceil(total_members / per_page)
    offset = (page - 1) * per_page
    paginated_members = members_data[offset : offset + per_page]

    return render_template(
        'members.html', 
        guild=guild_details, 
        members=paginated_members, 
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        guild_id=guild_id
    )

@app.route('/edit/<int:guild_id>/member/<int:user_id>', methods=['GET', 'POST'])
def edit_member(guild_id, user_id):
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối database!", "danger")
        return redirect(url_for('members', guild_id=guild_id))

    guild_details = discord_api_request(f"/guilds/{guild_id}")
    if not guild_details:
        flash("Không thể lấy thông tin server", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_balance_str = request.form.get('balance')
        fake_boosts_str = request.form.get('fake_boosts', '0')
        role_name = request.form.get('role_name')
        role_color = request.form.get('role_color')

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT balance FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
                user_data = cur.fetchone()
                old_balance = user_data['balance'] if user_data else 0
                
                new_balance = int(new_balance_str)
                new_fake_boosts = int(fake_boosts_str) if fake_boosts_str.isdigit() else 0
                amount_changed = new_balance - old_balance
                
                cur.execute("UPDATE users SET balance = %s, fake_boosts = %s WHERE user_id = %s AND guild_id = %s", (new_balance, new_fake_boosts, user_id, guild_id))

                if amount_changed != 0:
                     cur.execute("""
                        INSERT INTO transactions (guild_id, user_id, transaction_type, item_name, amount_changed, new_balance)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """, (guild_id, user_id, 'admin_edit', 'Manual Edit', amount_changed, new_balance))

                if role_name is not None and role_color is not None:
                    cur.execute("UPDATE custom_roles SET role_name = %s, role_color = %s WHERE user_id = %s AND guild_id = %s",
                                (role_name, role_color, user_id, guild_id))

            conn.commit()
            flash("Cập nhật thông tin thành viên thành công!", "success")
        except Exception as e:
            flash(f"Lỗi khi cập nhật: {e}", "danger")
            conn.rollback()
        finally:
            conn.close()
        return redirect(url_for('members', guild_id=guild_id))

    # GET
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = """
        SELECT u.*, cr.role_id, cr.role_name, cr.role_color, cr.role_style, cr.gradient_color_1, cr.gradient_color_2
        FROM users u
        LEFT JOIN custom_roles cr ON u.user_id = cr.user_id AND u.guild_id = cr.guild_id
        WHERE u.user_id = %s AND u.guild_id = %s;
        """
        cur.execute(query, (user_id, guild_id))
        user_db_data = cur.fetchone()
        
        cur.execute("SELECT * FROM transactions WHERE guild_id = %s AND user_id = %s ORDER BY timestamp DESC LIMIT 10", (guild_id, user_id))
        transactions = cur.fetchall()

    conn.close()

    if not user_db_data:
        with get_db_connection() as c:
            with c.cursor() as cur:
                cur.execute("INSERT INTO users (user_id, guild_id, balance) VALUES (%s, %s, 0) ON CONFLICT DO NOTHING", (user_id, guild_id))
                c.commit()
        return edit_member(guild_id, user_id)

    user_api_data = get_user_info(user_id)
    if not user_api_data:
        flash("Không thể lấy thông tin người dùng từ Discord.", "danger")
        return redirect(url_for('members', guild_id=guild_id))
        
    user_api_data['display_name'] = user_api_data.get('name')

    full_user_data = {**user_db_data, **user_api_data}

    return render_template('edit_member.html', guild=guild_details, user=full_user_data, transactions=transactions, guild_id=guild_id)

@app.route('/edit/<int:guild_id>/history')
def history(guild_id):
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối database!", "danger")
        return redirect(url_for('edit_config', guild_id=guild_id))

    guild_details = discord_api_request(f"/guilds/{guild_id}")
    if not guild_details:
        flash("Không thể lấy thông tin server", "danger")
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) as total FROM transactions WHERE guild_id = %s", (guild_id,))
        total_transactions = cur.fetchone()['total']
        
        cur.execute("SELECT * FROM transactions WHERE guild_id = %s ORDER BY timestamp DESC LIMIT %s OFFSET %s", (guild_id, per_page, offset))
        transactions_raw = cur.fetchall()
    conn.close()
    
    members_map = {}
    api_members = discord_api_request(f"/guilds/{guild_id}/members?limit=1000")
    if api_members:
        for member_data in api_members:
            user = member_data.get('user', {})
            user_id = user.get('id')
            if user_id:
                avatar_hash = user.get('avatar')
                members_map[int(user_id)] = {
                    'name': user.get('global_name') or user.get('username'),
                    'avatar_url': f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
                }

    transactions = []
    for t in transactions_raw:
        user_id = t['user_id']
        if user_id in members_map:
            t['user_info'] = members_map[user_id]
        else:
            t['user_info'] = get_user_info(user_id)
        transactions.append(t)

    total_pages = math.ceil(total_transactions / per_page)

    return render_template(
        'history.html', 
        guild=guild_details, 
        transactions=transactions,
        page=page,
        total_pages=total_pages,
        guild_id=guild_id
    )


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True, port=5001)