import os
import json
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash

# Tai bien moi truong tu file .env
load_dotenv()

app = Flask(__name__)
# Can co secret key de su dung flash message
app.config['SECRET_KEY'] = os.urandom(24)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Ham giup ket noi den database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Loi ket noi database: {e}")
        return None

@app.route('/')
def index():
    """Trang chu, hien thi danh sach cac server da co config."""
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return render_template('index.html', guilds=[])
        
    with conn.cursor() as cur:
        # Lay ID de hien thi, khong can lay data lon
        cur.execute("SELECT guild_id FROM guild_configs ORDER BY guild_id;")
        guilds_data = cur.fetchall()
    conn.close()
    
    # Chuyen doi du lieu de template de xu ly hon
    guilds = [{'guild_id': row[0]} for row in guilds_data]
    
    return render_template('index.html', guilds=guilds)


@app.route('/edit/<int:guild_id>', methods=['GET', 'POST'])
def edit_config(guild_id):
    """Trang chinh sua config cho mot server cu the."""
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Nhan du lieu tu form
        shop_channel_id = request.form.get('shop_channel_id')
        leaderboard_thread_id = request.form.get('leaderboard_thread_id')
        config_data_str = request.form.get('config_data')

        # Kiem tra tinh hop le cua JSON
        try:
            config_data_json = json.loads(config_data_str)
        except json.JSONDecodeError:
            flash("Lỗi: Dữ liệu cấu hình chi tiết không phải là JSON hợp lệ. Vui lòng kiểm tra lại.", "danger")
            # De nguoi dung khong mat du lieu da nhap, ta render lai trang voi du lieu cu
            return render_template('edit_config.html', guild_id=guild_id, 
                                   shop_channel_id=shop_channel_id,
                                   leaderboard_thread_id=leaderboard_thread_id,
                                   config_data_str=config_data_str)

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE guild_configs
                    SET shop_channel_id = %s, leaderboard_thread_id = %s, config_data = %s
                    WHERE guild_id = %s;
                    """,
                    (
                        shop_channel_id if shop_channel_id else None,
                        leaderboard_thread_id if leaderboard_thread_id else None,
                        Json(config_data_json),
                        guild_id
                    )
                )
            conn.commit()
            flash(f"Đã cập nhật thành công cấu hình cho Server ID: {guild_id}", "success")
        except Exception as e:
            flash(f"Lỗi khi cập nhật database: {e}", "danger")
        finally:
            conn.close()
        
        return redirect(url_for('index'))

    # Xu ly cho GET request
    with conn.cursor() as cur:
        cur.execute("SELECT shop_channel_id, leaderboard_thread_id, config_data FROM guild_configs WHERE guild_id = %s;", (guild_id,))
        config = cur.fetchone()
    conn.close()

    if not config:
        flash(f"Không tìm thấy cấu hình cho Server ID: {guild_id}", "warning")
        return redirect(url_for('index'))

    shop_channel_id, leaderboard_thread_id, config_data = config
    
    # Chuyen JSON thanh chuoi dinh dang dep de hien thi trong textarea
    config_data_str = json.dumps(config_data, indent=2, ensure_ascii=False)

    return render_template('edit_config.html', guild_id=guild_id, 
                           shop_channel_id=shop_channel_id,
                           leaderboard_thread_id=leaderboard_thread_id,
                           config_data_str=config_data_str)

if __name__ == '__main__':
    # Chay app o che do debug de de phat trien
    app.run(debug=True, port=5001)