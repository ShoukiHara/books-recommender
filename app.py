import streamlit as st
import pandas as pd
import database as db
import logic
import os

import streamlit_javascript as st_js

# --- 設定と初期化 ---
st.set_page_config(page_title="🎓BG参考書データベース", page_icon="📚", layout="wide")

# カスタムCSS
st.markdown("""
<style>
    .book-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 5px solid #4CAF50;
    }
    .book-card h3 {
        margin-top: 0;
        color: #2e7d32;
    }
    .rank-badge {
        display: inline-block;
        background-color: #ff9800;
        color: white;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: bold;
        margin-right: 10px;
    }
    .rank-1 { background-color: #ffd700; color: #333; }
    .rank-2 { background-color: #c0c0c0; color: #333; }
    .rank-3 { background-color: #cd7f32; color: white; }

    .shop-btn {
        display: inline-block;
        padding: 8px 15px;
        border-radius: 5px;
        text-decoration: none;
        font-weight: bold;
        margin-right: 10px;
        margin-top: 10px;
    }
    .btn-amazon { background-color: #ff9900; color: white; }
    .btn-rakuten { background-color: #bf0000; color: white; }

    .layer-badge {
        background-color: #e3f2fd;
        color: #1565c0;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8em;
    }

    .score-text {
        font-size: 1.2em;
        font-weight: bold;
        color: #d32f2f;
    }
</style>
""", unsafe_allow_html=True)

# DB初期化
@st.cache_resource
def init_system():
    db.init_db()
    return True

init_system()

# セッションステートの初期化
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'main'
if 'selected_book_id' not in st.session_state:
    st.session_state.selected_book_id = None
if 'diagnosis_result' not in st.session_state:
    st.session_state.diagnosis_result = None
if 'is_admin_authenticated' not in st.session_state:
    st.session_state.is_admin_authenticated = False

def get_secret_val(key, default_val):
    if key in st.secrets:
        return st.secrets[key]
    if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        if key in st.secrets["connections"]["gsheets"]:
            return st.secrets["connections"]["gsheets"][key]
    return os.environ.get(key, default_val)

# 環境変数などから管理者パスワードを取得（Streamlit Cloudでは Secrets を優先）
ADMIN_PASSWORD = get_secret_val("ADMIN_PASSWORD", "admin123")

# Gemini APIキーの設定
GEMINI_API_KEY = get_secret_val("GEMINI_API_KEY", "AIzaSyBLRH_C6niZZUfLREmfsq-z00Vwdj8oZrk")

# 科目リスト
SUBJECTS = ["英語", "文系数学", "理系数学", "現代文", "古文", "漢文", "物理", "化学", "生物", "日本史", "世界史", "地理", "倫理・政治経済"]
LAYERS = {
    1: "予習・初学フェーズ",
    2: "基礎力完成フェーズ (地方国公立ゴール)",
    3: "応用・発展フェーズ (阪大以上ゴール)"
}

# --- サイドバー (ルーティング) ---
st.sidebar.title("ナビゲーション")

if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "生徒用：リコメンド診断"

mode = st.sidebar.selectbox("モード選択", ["生徒用：リコメンド診断", "生徒用：参考書一覧", "講師用：データ入力", "管理：データベース編集"], key="app_mode")

# --- ビュー切り替え関数 ---
def scroll_to_top():
    st_js.st_javascript("window.scrollTo(0, 0);")

def go_to_main():
    st.session_state.current_view = 'main'
    st.session_state.selected_book_id = None
    scroll_to_top()

def go_to_detail(book_id):
    st.session_state.current_view = 'detail'
    st.session_state.selected_book_id = book_id
    scroll_to_top()

def go_to_review_form(book_id, subject):
    st.session_state.previous_mode = st.session_state.app_mode
    st.session_state.app_mode = "講師用：データ入力"
    st.session_state.instructor_action = "レビューの投稿"
    st.session_state.review_subject = subject
    st.session_state.preset_review_book_id = book_id
    st.session_state.current_view = 'main'
    scroll_to_top()

def return_from_review_form():
    if 'previous_mode' in st.session_state:
        st.session_state.app_mode = st.session_state.previous_mode
        del st.session_state.previous_mode
    st.session_state.current_view = 'detail'
    scroll_to_top()

# ---------------------------------------------------------
# 生徒用モード
# ---------------------------------------------------------
def render_student_mode():
    if st.session_state.current_view == 'main':
        st.title("🎓BG参考書データベース")
        st.write("担当生徒の学力や悩みに合わせて、最適な参考書をAIが診断・推薦します。")

        tab1, tab2 = st.tabs(["🤖 AIに診断してもらう", "🎯 自分でレベルを指定する"])

        with tab1:
            with st.form("diagnosis_form"):
                subject = st.selectbox("学習したい科目", SUBJECTS)
                grade = st.selectbox("学年", ["高1", "高2", "高3", "既卒"])
                target_univ = st.text_input("志望校", placeholder="例：京都大学")
                mock_score = st.text_input("現在の模試の成績 (偏差値や判定など)", placeholder="例：全統模試 英語 偏差値60")
                current_books = st.text_area("現在使用している参考書の名前とその完成度", placeholder="例：システム英単語 1章から2章まで完璧。基礎英文解釈の技術100 1週目")
                student_worry = st.text_area("現在の悩みや学習状況を具体的に書いてください",
                                            placeholder="例：英語の長文になると読むのが遅くなってしまう。")
                submit_btn = st.form_submit_button("診断する")

            if submit_btn and student_worry:
                with st.spinner("AIがあなたの学習レベルを分析中..."):

                    # 情報を結合してAIに渡す
                    combined_info = f"学年: {grade}\n志望校: {target_univ}\n模試成績: {mock_score}\n使用参考書と完成度: {current_books}\n悩み・状況: {student_worry}"

                    layer, reason = logic.classify_student_layer(GEMINI_API_KEY, combined_info)
                    st.session_state.diagnosis_result = {
                        'subject': subject,
                        'layer': layer,
                        'reason': reason
                    }

            if st.session_state.diagnosis_result:
                res = st.session_state.diagnosis_result
                if res['subject'] == subject:
                    st.success(f"**診断結果：** {LAYERS[res['layer']]}")
                    st.info(f"**理由：** {res['reason']}")

                    # ランキングの計算を先に行ってダウンロード用テキストを生成する
                    rankings = logic.calculate_ranking(subject, res['layer'])
                    
                    # ダウンロード用テキストの生成
                    download_text = f"【AI参考書リコメンダー 診断結果】\n"
                    download_text += "-" * 30 + "\n"
                    download_text += f"対象科目: {subject}\n"
                    download_text += f"推奨レベル: {LAYERS[res['layer']]}\n"
                    download_text += f"診断理由: {res['reason']}\n"
                    download_text += "-" * 30 + "\n\n"
                    download_text += "【おすすめ参考書 TOP10】\n"
                    
                    if rankings:
                        for i, book in enumerate(rankings[:10]):
                            download_text += f"{i+1}位: {book['title']} (平均評価: {book['avg_rating']:.1f})\n"
                    else:
                        download_text += "該当するレベルのレビュー済み参考書がありません。\n"
                        
                    st.download_button(
                        label="📄 診断結果をテキストで保存",
                        data=download_text,
                        file_name=f"ai_diagnosis_{subject}.txt",
                        mime="text/plain"
                    )

                    # 実際のランキングUIを描画する
                    st.subheader(f"🏆 {subject} - {LAYERS[res['layer']]} おすすめランキング TOP10")
                    if not rankings:
                         st.warning("この科目・レベルに対するレビューがまだありません。")
                    else:
                        for i, book in enumerate(rankings[:10]):
                            rank_idx = i + 1
                            rank_class = f"rank-{rank_idx}" if rank_idx <= 3 else "rank-other"
                    
                            st.markdown(f'''
                            <div class="book-card">
                                <h3><span class="rank-badge {rank_class}">{rank_idx}位</span> {book['title']}</h3>
                                <p>
                                    <span class="score-text">⭐ {book['score']:.2f}</span>
                                    (平均評価: {book['avg_rating']:.1f} / レビュー数: {book['review_count']}件)
                                </p>
                            </div>
                            ''', unsafe_allow_html=True)
                    
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                st.button("詳細を見る", key=f"btn_ai_{book['book_id']}_{i}", on_click=go_to_detail, args=(book['book_id'],))

        with tab2:
            st.write("現在の自分の学習状況から、対応するレベルを直接指定して参考書を探します。")
            st.info("""
            **【レイヤーの目安】**
            - **予習・初学フェーズ:** 本格的な受験勉強を始める前の基礎固めや、学校の授業の予習復習レベル
            - **基礎力完成フェーズ:** 基礎が固まり、入試標準問題に対応できるレベル（地方国公立大学の合格ライン）
            - **応用・発展フェーズ:** 高い思考力が求められる実戦・過去問レベル（大阪大学以上の難関国公立大学の合格ライン）
            """)

            manual_subject = st.selectbox("科目を選択", SUBJECTS, key="manual_subject")
            manual_layer = st.radio("現在のレイヤーを選択", options=[1, 2, 3], format_func=lambda x: LAYERS[x])

            if st.button("この条件で検索"):
                st.session_state.manual_ranking_result = {'subject': manual_subject, 'layer': manual_layer}

            if 'manual_ranking_result' in st.session_state:
                res = st.session_state.manual_ranking_result
                render_ranking(res['subject'], res['layer'])

    elif st.session_state.current_view == 'detail':
        render_book_detail()

def render_ranking(subject, layer):
    st.subheader(f"🏆 {subject} - {LAYERS[layer]} おすすめランキング TOP10")

    rankings = logic.calculate_ranking(subject, layer)

    if not rankings:
        st.warning("この科目・レベルに対するレビューがまだありません。")
        return

    for i, book in enumerate(rankings[:10]):
        rank_idx = i + 1
        rank_class = f"rank-{rank_idx}" if rank_idx <= 3 else "rank-other"

        st.markdown(f"""
        <div class="book-card">
            <h3><span class="rank-badge {rank_class}">{rank_idx}位</span> {book['title']}</h3>
            <p>
                <span class="score-text">⭐ {book['score']:.2f}</span>
                (平均評価: {book['avg_rating']:.1f} / レビュー数: {book['review_count']}件)
            </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([1, 4])
        with col1:
            st.button("詳細を見る", key=f"btn_manual_{book['book_id']}_{i}", on_click=go_to_detail, args=(book['book_id'],))

def render_book_detail():
    if mode == "生徒用：参考書一覧":
        st.button("← 一覧に戻る", on_click=go_to_main)
    else:
        st.button("← ランキングに戻る", on_click=go_to_main)

    book_id = st.session_state.selected_book_id
    book = db.get_book_by_id(book_id)

    if not book:
        st.error("参考書が見つかりません。")
        return

    st.title(f"📖 {book['title']}")
    st.markdown(f"<span class='layer-badge'>{book['subject']}</span>", unsafe_allow_html=True)

    # ショッピングリンク
    links = logic.get_shopping_links(book['title'])
    st.markdown(f"""
    <div style="margin: 20px 0 10px 0;">
        <a href="{links['Amazon']}" target="_blank" class="shop-btn btn-amazon">🛒 Amazonで探す</a>
        <a href="{links['Rakuten']}" target="_blank" class="shop-btn btn-rakuten">🛒 楽天市場で探す</a>
    </div>
    """, unsafe_allow_html=True)

    # レビュー投稿ボタン
    st.button("📝 この参考書にコメントをする", type="primary", on_click=go_to_review_form, args=(book['book_id'], book['subject']))
    st.markdown("<br>", unsafe_allow_html=True)
    reviews_df = db.get_reviews_by_book(book_id)

    # AI学習アドバイス
    st.subheader("🤖 AI学習アドバイス")
    with st.spinner("レビューからアドバイスを生成中..."):
        guide = logic.generate_book_guide(GEMINI_API_KEY, book['title'], reviews_df)
        st.info(guide)

    # レビュー一覧
    st.subheader("👨‍🏫 講師陣のレビュー")
    if reviews_df.empty:
        st.write("まだレビューがありません。")
    else:
        for _, review in reviews_df.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**{review['instructor_name']} 先生**")
                with col2:
                    st.markdown(f"対象: {LAYERS[review['layer']]}")
                with col3:
                    st.markdown(f"評価: {'⭐'*int(review['rating'])}")

                # st.write だと改行がスペースになることがあるため、改行を維持して表示
                st.markdown(review['comment'].replace('\n', '  \n'))

    # 類似参考書の表示
    st.markdown("---")
    st.subheader("📚 同じ科目のその他の参考書")
    similar_books_df = db.get_books_by_subject(book['subject'])
    # 現在表示中の参考書を除外
    similar_books_df = similar_books_df[similar_books_df['book_id'] != book_id]
    
    if similar_books_df.empty:
        st.write("同じ科目の他の参考書はまだ登録されていません。")
    else:
        # 最大5件まで表示
        for _, row in similar_books_df.head(5).iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{row['title']}**")
                with col2:
                    st.button("詳細を見る", key=f"sim_btn_{row['book_id']}_{_}", on_click=go_to_detail, args=(row['book_id'],))

# ---------------------------------------------------------
# 講師用モード
# ---------------------------------------------------------
def render_instructor_mode():
    st.title("👨‍🏫 講師用：データ入力画面")

    if 'instructor_action' not in st.session_state:
        st.session_state.instructor_action = "レビューの投稿"

    st.write("実行したい操作を選択してください：")
    action = st.radio("メニュー", ["レビューの投稿", "参考書の登録"], horizontal=True, key="instructor_action", label_visibility="collapsed")
    st.markdown("---")

    # --- 参考書登録 ---
    if action == "参考書の登録":
        # リアルタイム検索のためにフォームを使わず通常のウィジェットを使用
        new_title = st.text_input("参考書名", key="new_book_title")
        
        # 重複チェック・サジェスト機能
        if new_title:
            all_books_df = db.get_books_table()
            if not all_books_df.empty:
                # 入力された文字列が含まれる参考書を検索
                matches = all_books_df[all_books_df['title'].str.contains(new_title, na=False, case=False)]
                if not matches.empty:
                    st.warning("⚠️ 似た名前の参考書が既に登録されている可能性があります。")
                    for _, row in matches.head(3).iterrows():
                        st.write(f"- {row['title']} ({row['subject']})")

        # 科目リストの一番上に「英語」、その次に数学系が来るように自然に並び替える
        reg_subjects = ["英語", "文理共通数学", "文系数学", "理系数学", "現代文", "古文", "漢文", "物理", "化学", "生物", "日本史", "世界史", "地理", "倫理・政治経済"]
        
        new_subject = st.selectbox("科目", reg_subjects, key="book_subject")
        book_submit = st.button("登録する", type="primary")

        if book_submit:
            if not new_title:
                st.error("参考書名を入力してください。")
            else:
                if new_subject == "文理共通数学":
                    res1 = db.add_book(new_title, "文系数学")
                    res2 = db.add_book(new_title, "理系数学")
                    if res1 or res2:
                        st.success(f"「{new_title}」を文系・理系両方に登録しました！")
                    else:
                        st.warning("この参考書は既に両方に登録されています。")
                else:
                    res = db.add_book(new_title, new_subject)
                    if res:
                        st.success(f"「{new_title}」を登録しました！")
                    else:
                        st.warning("この参考書は既に登録されています。")

    # --- レビュー投稿 ---
    elif action == "レビューの投稿":
        st.subheader("レビューの投稿")
        
        if 'previous_mode' in st.session_state:
            st.button("← 参考書詳細に戻る", key="back_to_detail_top", on_click=return_from_review_form)

        st.info(
            "**【入力時のお願いとルール】**\n\n"
            "- ① **必須項目:** 「講師名」と「レビューコメント」は必ずご記入ください。講師名を書くのが憚られる場合は「匿名」でも構いません。\n"
            "- ② **重複防止:** 各参考書の「各レイヤー」に対する評価は、1人1回までとしてください。\n"
            "- ③ **星の評価基準:** 星0は「不適切」、星5は「最適」という評価です。特徴をはっきりさせるため、星3ばかりにせず**できるだけ極端に点数をつけて**ください。\n"
            "- ④ **詳細な入力:** ご自身が使用していた参考書をレビューする場合は、使用していた時期、期間、感想をコメントしてくれると助かります！（AIが自動であなたのコメントを反映して参考書サマリーを作成します）"
        )

        book_subject = st.selectbox("対象科目で絞り込み", SUBJECTS, key="review_subject")
        books_df = db.get_books_by_subject(book_subject)

        if books_df.empty:
            st.info("この科目の参考書はまだ登録されていません。先に「参考書の登録」から追加してください。")
        else:
            book_options = {row['book_id']: row['title'] for _, row in books_df.iterrows()}

            instructor_list = db.get_instructor_names()
            if not instructor_list:
                st.warning("現在登録されている講師がいません。まずは管理者画面から講師名を登録してください。")
                st.stop()
                
            # preset_review_book_idが存在する場合は、そのインデックスをデフォルトにする
            default_index = 0
            if 'preset_review_book_id' in st.session_state:
                preset_id = st.session_state.preset_review_book_id
                keys_list = list(book_options.keys())
                if preset_id in keys_list:
                    default_index = keys_list.index(preset_id)
                del st.session_state.preset_review_book_id # Clear after using it once

            selected_book_id = st.selectbox("参考書を選択", options=list(book_options.keys()), format_func=lambda x: book_options[x], index=default_index)
            instructor_name = st.selectbox("講師を選択", options=instructor_list)
            layer_choice = st.radio("学習者レイヤー", options=[1, 2, 3], format_func=lambda x: LAYERS[x], horizontal=True)

            # 評価点を星の数から選択 (クリックで直感的に入力)
            st.write("評価")
            star_rating = st.feedback("stars")
            # st.feedback("stars") は 0〜4 または None を返すため、1〜5に変換。未入力時はデフォルト0。
            rating = (star_rating + 1) if star_rating is not None else 0

            default_comment_template = (
                "・使用していた時期と期間：\n\n"
                "・この参考書をやる前に使用していた参考書と接続のスムーズさ：\n\n"
                "・この参考書の後に使用していた参考書と接続のスムーズさ：\n\n"
                "・使用感：\n"
            )
            
            # keyを指定することでsession_stateに自動保存され、他ページから戻った時も破棄されるまで状態を保持できる可能性が高まる
            comment = st.text_area("レビューコメント（具体的な使い方や特徴など）", value=default_comment_template, height=300, key="draft_review_comment")

            with st.expander("📝 プレビュー (マークダウン)"):
                if st.session_state.draft_review_comment:
                    st.markdown(st.session_state.draft_review_comment.replace('\n', '  \n'))
                else:
                    st.write("コメントを入力するとここにプレビューが表示されます。")

            review_submit = st.button("レビューを投稿", type="primary", key="submit_review_btn")

            if review_submit:
                if not instructor_name or not comment:
                    st.error("講師名とコメントは必須です。")
                else:
                    db.add_review(selected_book_id, instructor_name, layer_choice, rating, comment)
                    st.success("レビューを投稿しました。ありがとうございます！")
                    if 'previous_mode' in st.session_state:
                        st.button("← 参考書詳細に戻る", type="secondary", key="back_to_detail_bottom", on_click=return_from_review_form)

# ---------------------------------------------------------
# 生徒用参考書一覧モード
# ---------------------------------------------------------
def render_book_list_mode():
    if st.session_state.current_view == 'detail':
        render_book_detail()
        return

    st.title("📚 参考書一覧")
    st.write("登録されているすべての参考書を科目別に見ることができます。")

    col1, col2 = st.columns(2)
    with col1:
        selected_subject = st.selectbox("科目で絞り込む", ["すべて"] + SUBJECTS)
    with col2:
        sort_order = st.selectbox("並び替え", ["タイトル順", "評価が高い順", "レビューが多い順"])
        only_reviewed = st.checkbox("レビューのついている参考書のみ表示")

    books_df = db.get_books_by_subject(selected_subject) if selected_subject != "すべて" else db.get_books_by_subject("")
    # If "" is passed, get_books_by_subject returns all books since we filter by wildcard
    # SQLite時代の get_db_connection は廃止されたため、GSheetsから全件取得してPandasで処理する
    if selected_subject == "すべて":
        books_df = db.get_books_table()
        if not books_df.empty:
            books_df = books_df.sort_values(by=['subject', 'title'])
    else:
        books_df = db.get_books_by_subject(selected_subject)
        if not books_df.empty:
            books_df = books_df.sort_values(by=['title'])
            
    if books_df.empty:
        st.info("参考書がまだ登録されていません。")
        return

    # レビューデータの結合と集計（ソートやレイヤー絞り込みに必要）
    reviews_df = db.get_reviews_data()
    
    if not reviews_df.empty:
        # レビュー絞り込み
        if only_reviewed:
            reviewed_book_ids = reviews_df['book_id'].unique()
            books_df = books_df[books_df['book_id'].isin(reviewed_book_ids)]

        # 各参考書の平均評価とレビュー数を計算してマージ
        book_stats = reviews_df.groupby('book_id').agg(
            avg_rating=('rating', 'mean'),
            review_count=('review_id', 'count')
        ).reset_index()
        books_df = pd.merge(books_df, book_stats, on='book_id', how='left')
        books_df['avg_rating'] = books_df['avg_rating'].fillna(0)
        books_df['review_count'] = books_df['review_count'].fillna(0)
    else:
        # レビューが1件もない場合
        if only_reviewed:
            books_df = pd.DataFrame() # 条件を満たす本は存在し得ない
        else:
            books_df['avg_rating'] = 0
            books_df['review_count'] = 0

    if books_df.empty:
        st.info("条件に一致する参考書はありません。")
        return

    # 並び替え実行
    if sort_order == "評価が高い順":
        books_df = books_df.sort_values(by=['avg_rating', 'review_count', 'title'], ascending=[False, False, True])
    elif sort_order == "レビューが多い順":
        books_df = books_df.sort_values(by=['review_count', 'avg_rating', 'title'], ascending=[False, False, True])
    else: # タイトル順
        books_df = books_df.sort_values(by=['subject', 'title'] if selected_subject == "すべて" else ['title'])

    for subject, group in books_df.groupby('subject', sort=(sort_order == "タイトル順")):
        st.subheader(f"■ {subject}")
        for _, row in group.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    if sort_order in ["評価が高い順", "レビューが多い順"] and 'avg_rating' in row:
                        st.markdown(f"**{row['title']}** (⭐ {row['avg_rating']:.1f} / {int(row['review_count'])}件)")
                    else:
                        st.markdown(f"**{row['title']}**")
                with col2:
                    st.button("詳細を見る", key=f"list_btn_{row['book_id']}_{_}", on_click=go_to_detail, args=(row['book_id'],))

# ---------------------------------------------------------
# 管理モード
# ---------------------------------------------------------
def render_admin_mode():
    st.title("🛠 管理：データベース編集")

    # 認証チェック
    if not st.session_state.is_admin_authenticated:
        st.warning("このページは管理者専用です。パスワードを入力してください。")
        with st.form("admin_login_form"):
            password_input = st.text_input("管理者パスワード", type="password")
            login_submit = st.form_submit_button("ログイン")

            if login_submit:
                if password_input == ADMIN_PASSWORD:
                    st.session_state.is_admin_authenticated = True
                    st.success("認証に成功しました！")
                    st.rerun() # ページをリロードして管理画面を表示
                else:
                    st.error("パスワードが間違っています。")
        return # 認証されていない場合はここで描画を終了する

    # 認証成功後のUI
    col1, col2 = st.columns([4, 1])
    with col1:
        st.write("登録されているレビューデータを編集・削除できます。")
    with col2:
        if st.button("ログアウト"):
            st.session_state.is_admin_authenticated = False
            st.rerun()

    # データを取得して DataFrame でコピー
    reviews_df = db.get_reviews_data()

    if reviews_df.empty:
        st.info("登録されているデータはありません。")
        return

    st.dataframe(reviews_df, use_container_width=True)

    st.divider()

    st.subheader("講師マスタの管理")
    instructors = db.get_instructor_names()
    
    col_inst1, col_inst2 = st.columns(2)
    with col_inst1:
        st.write("**登録済み講師一覧**")
        if instructors:
            st.write(", ".join(instructors))
        else:
            st.write("登録されている講師はいません。")
            
        with st.expander("新規講師の追加"):
            new_inst_name = st.text_input("追加する講師名")
            if st.button("講師を追加"):
                if new_inst_name:
                    if db.add_instructor(new_inst_name):
                        st.success(f"「{new_inst_name}」を追加しました。")
                        st.rerun()
                    else:
                        st.error("すでに追加されているか、追加エラーです。")
                else:
                    st.error("講師名を入力してください。")
                    
    with col_inst2:
        with st.expander("講師の削除"):
            if instructors:
                del_inst_name = st.selectbox("削除する講師を選択", options=instructors)
                if st.button("講師を削除", type="primary"):
                    if db.delete_instructor(del_inst_name):
                        st.success(f"「{del_inst_name}」を削除しました。")
                        st.rerun()
                    else:
                        st.error("削除に失敗しました。")
            else:
                st.info("削除可能な講師がいません。")

    st.divider()

    st.subheader("レビューの編集・削除")

    review_ids = reviews_df['review_id'].tolist()

    col1, col2 = st.columns(2)

    with col1:
        edit_id = st.selectbox("編集/削除するレビューID", review_ids)

        target_review = reviews_df[reviews_df['review_id'] == edit_id].iloc[0]

        with st.form("edit_delete_form"):
            st.write(f"**対象:** {target_review['title']} ({target_review['instructor_name']})")

            new_layer = st.selectbox("レイヤー", options=[1, 2, 3], index=[1, 2, 3].index(target_review['layer']))
            new_rating = st.slider("評価", 0, 5, value=int(target_review['rating']))
            new_comment = st.text_area("コメント", value=target_review['comment'])

            update_btn = st.form_submit_button("更新保存")
            delete_btn = st.form_submit_button("⚠️ 削除", type="primary")

            if update_btn:
                res = db.update_review(edit_id, new_layer, new_rating, new_comment)
                if res:
                    st.success("更新しました！更新を反映するにはページをリロードしてください。")

            if delete_btn:
                res = db.delete_review(edit_id)
                if res:
                    st.success("削除しました！更新を反映するにはページをリロードしてください。")

# --- メイン実行処理 ---
if mode == "生徒用：リコメンド診断":
    render_student_mode()
elif mode == "生徒用：参考書一覧":
    render_book_list_mode()
elif mode == "講師用：データ入力":
    render_instructor_mode()
elif mode == "管理：データベース編集":
    render_admin_mode()
