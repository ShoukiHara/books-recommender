import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# ------------------------------------------------------------------
# 初期データのカラム定義
# ------------------------------------------------------------------
def get_empty_books_df():
    return pd.DataFrame(columns=['book_id', 'title', 'subject'])

def get_empty_reviews_df():
    return pd.DataFrame(columns=['review_id', 'book_id', 'instructor_name', 'layer', 'rating', 'comment', 'likes'])

# ------------------------------------------------------------------
# DBアクセス層 (Google Spreadsheets)
# ------------------------------------------------------------------
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

def get_books_table():
    try:
        df = get_conn().read(worksheet="books", ttl=0)
        # Ensure it's not empty and all string columns meant for ids are processed correctly.
        if df.empty or 'book_id' not in df.columns:
            return get_empty_books_df()
        return df.dropna(how="all") # Drop completely empty rows
    except Exception as e:
        st.error(f"Booksシートの読み込みに失敗しました: {e}\n設定ファイル(secrets.toml)とシート名を確認してください。")
        return get_empty_books_df()

def get_reviews_table():
    try:
        df = get_conn().read(worksheet="reviews", ttl=0)
        if df.empty or 'review_id' not in df.columns:
            return get_empty_reviews_df()
        return df.dropna(how="all")
    except Exception as e:
        st.error(f"Reviewsシートの読み込みに失敗しました: {e}\n設定ファイル(secrets.toml)とシート名を確認してください。")
        return get_empty_reviews_df()

def _save_books_table(df):
    get_conn().update(worksheet="books", data=df)

def _save_reviews_table(df):
    get_conn().update(worksheet="reviews", data=df)

# ------------------------------------------------------------------
# ID採番ユーティリティ
# ------------------------------------------------------------------
def _get_next_id(df, id_column):
    if df.empty:
        return 1
    # Convert to numeric explicitly to avoid string max comparison issues
    numeric_ids = pd.to_numeric(df[id_column], errors='coerce').fillna(0)
    return int(numeric_ids.max()) + 1

# ------------------------------------------------------------------
# CRUD Operations
# ------------------------------------------------------------------
def add_book(title, subject):
    """新しい参考書を追加する"""
    df = get_books_table()
    
    # Check if duplicate exists
    if not df.empty:
        duplicates = df[(df['title'] == title) & (df['subject'] == subject)]
        if not duplicates.empty:
            return None # 既に存在している
            
    new_id = _get_next_id(df, 'book_id')
    new_row = pd.DataFrame([{'book_id': new_id, 'title': title, 'subject': subject}])
    df = pd.concat([df, new_row], ignore_index=True)
    _save_books_table(df)
    return new_id

def add_review(book_id, instructor_name, layer, rating, comment):
    """新しいレビューを追加する"""
    df = get_reviews_table()
    new_id = _get_next_id(df, 'review_id')
    new_row = pd.DataFrame([{
        'review_id': new_id,
        'book_id': book_id,
        'instructor_name': instructor_name,
        'layer': layer,
        'rating': rating,
        'comment': comment,
        'likes': 0
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    _save_reviews_table(df)
    return new_id

def update_review(review_id, layer, rating, comment):
    """既存のレビューを更新する"""
    df = get_reviews_table()
    if df.empty: return False
    
    # string/number cast handling
    target_idx = df.index[df['review_id'].astype(str) == str(review_id)].tolist()
    if not target_idx:
        return False
        
    idx = target_idx[0]
    df.at[idx, 'layer'] = layer
    df.at[idx, 'rating'] = rating
    df.at[idx, 'comment'] = comment
    _save_reviews_table(df)
    return True

def delete_review(review_id):
    """レビューを削除する"""
    df = get_reviews_table()
    if df.empty: return False
    
    initial_len = len(df)
    df = df[df['review_id'].astype(str) != str(review_id)]
    
    if len(df) < initial_len:
        _save_reviews_table(df)
        return True
    return False

def add_like(review_id):
    """レビューのいいね数をインクリメントする"""
    df = get_reviews_table()
    if df.empty: return False
    
    target_idx = df.index[df['review_id'].astype(str) == str(review_id)].tolist()
    if not target_idx:
        return False
        
    idx = target_idx[0]
    current_likes = int(float(df.at[idx, 'likes'])) if pd.notna(df.at[idx, 'likes']) and str(df.at[idx, 'likes']).strip() != '' else 0
    df.at[idx, 'likes'] = current_likes + 1
    _save_reviews_table(df)
    return True

# ------------------------------------------------------------------
# Retrieval Operations
# ------------------------------------------------------------------
def get_books_by_subject(subject):
    """指定された科目の参考書一覧を取得する。空文字の場合はすべて返す。"""
    df = get_books_table()
    if df.empty: return get_empty_books_df()
    
    if subject == "" or subject == "すべて":
        return df
    return df[df['subject'] == subject]

def get_book_by_id(book_id):
    """IDから参考書情報をディクショナリで取得する"""
    df = get_books_table()
    if df.empty: return None
    
    result = df[df['book_id'].astype(str) == str(book_id)]
    if not result.empty:
        return result.iloc[0].to_dict()
    return None

def get_reviews_data():
    """全レビューデータと紐づく参考書情報を結合して取得する"""
    books_df = get_books_table()
    reviews_df = get_reviews_table()
    
    if books_df.empty or reviews_df.empty:
        return pd.DataFrame(columns=['review_id', 'book_id', 'title', 'subject', 'instructor_name', 'layer', 'rating', 'comment', 'likes'])
        
    # Convert book_id to string matching types for merge
    books_df['book_id_str'] = books_df['book_id'].astype(str)
    reviews_df['book_id_str'] = reviews_df['book_id'].astype(str)
    
    merged = pd.merge(reviews_df, books_df, on='book_id_str', how='inner')
    merged = merged.drop(columns=['book_id_str', 'book_id_y'])
    merged = merged.rename(columns={'book_id_x': 'book_id'})
    
    # layer/rating を数値型に確実に変換
    merged['layer'] = pd.to_numeric(merged['layer'], errors='coerce')
    merged['rating'] = pd.to_numeric(merged['rating'], errors='coerce')
    merged['likes'] = pd.to_numeric(merged['likes'], errors='coerce').fillna(0)
    
    return merged

def get_reviews_by_book(book_id):
    """特定の参考書のレビュー一覧を取得する"""
    df = get_reviews_table()
    if df.empty: return get_empty_reviews_df()
    
    return df[df['book_id'].astype(str) == str(book_id)]

def get_instructor_counts():
    """講師ごとの累計レビュー数を辞書で取得する"""
    df = get_reviews_table()
    if df.empty: return {}
    
    # 講師名でグループ化してカウント
    counts = df.groupby('instructor_name').size().to_dict()
    return counts

def init_db():
    """SQLite時代の名残。GSheetsでは初期化不要（シート作成はユーザーが行う）。"""
    pass
