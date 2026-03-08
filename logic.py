import numpy as np
import urllib.parse
import google.generativeai as genai
from google.generativeai import types
import database as db
import re

def classify_student_layer(api_key, student_info):
    """
    生徒の悩みテキストから学習段階(1〜3)を判定し、数値と理由のテキストを返す。
    layer: 1(初学), 2(標準), 3(上位)
    """
    if not api_key:
        return 1, "APIキーが設定されていないため、デフォルトの「初学」レイヤーと判定しました。"
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f'''
        あなたはプロの学習アドバイザーです。以下の生徒の悩みや学習状況を読み、
        その生徒の現在の学習段階（レイヤー）を1〜3の数値で判定してください。
        
        レイヤー定義:
        1: 予習・初学フェーズ（本格的な受験勉強を始める前の基礎固めや、学校の授業の予習復習レベル）
        2: 基礎力完成フェーズ（基礎が固まり、入試標準問題に対応できるレベル。地方国公立大学の合格ライン）
        3: 応用・発展フェーズ（高い思考力が求められる実戦・過去問レベル。大阪大学以上の難関国公立大学の合格ライン）
        
        【生徒の状況】
        {student_info}
        
        出力形式:
        レイヤー: [1, 2, 3のいずれかの数字]
        理由: [判定した理由を簡潔に]
        '''
        
        response = model.generate_content(prompt)
        
        text = response.text
        layer_match = re.search(r'レイヤー:\s*([1-3])', text)
        layer = int(layer_match.group(1)) if layer_match else 1
        
        reason_match = re.search(r'理由:\s*(.*)', text, re.DOTALL)
        reason = reason_match.group(1).strip() if reason_match else text
        
        return layer, reason
        
    except Exception as e:
        return 1, f"判定エラーが発生しました: {str(e)}。デフォルトの「初学」レイヤーと判定しました。"

def generate_book_guide(api_key, title, reviews_df):
    """
    講師のレビュー群をもとに、参考書の特徴と使い方を200文字程度でAIに生成させる。
    """
    if not api_key:
        return "APIキーが設定されていません。AIガイドは利用できません。"
    
    if reviews_df.empty:
        return "まだレビューがありません。"
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        comments = "\n".join([f"- {row['instructor_name']}: {row['comment']}" for _, row in reviews_df.iterrows() if row['comment']])
        
        prompt = f'''
        あなたはプロのAI学習アドバイザーです。
        参考書「{title}」について、当塾の講師陣から寄せられた以下の【実際のレビュー】を統合し、
        この参考書の特徴とおすすめの使い方を200文字程度で簡潔に要約・解説してください。
        読者は個別指導塾の講師です。論理的で硬派な文章（である・だ調）で記述してください。

        【絶対厳守のルール】
        1. 送信されたレビューの内容「のみ」を事実として扱い、要約すること。
        2. 林修、関正生、竹岡広信などの「実在する有名な予備校講師」の名前やキャラクターを絶対に出さないこと。
        3. 「ある講師によると〜」「〜先生は〜」といった表現を避け、AIとしての客観的な分析としてまとめること。
        
        【実際のレビュー】
        {comments}
        '''
        
        response = model.generate_content(prompt)
        
        return response.text
        
    except Exception as e:
        return f"ガイド生成エラー: {str(e)}"

def get_shopping_links(title):
    """
    Amazonと楽天の検索URL（URLエンコード済）を辞書形式で返す。
    """
    encoded_title = urllib.parse.quote(title)
    
    return {
        'Amazon': f"https://www.amazon.co.jp/s?k={encoded_title}&i=stripbooks",
        'Rakuten': f"https://search.rakuten.co.jp/search/mall/{encoded_title}/200162/" # 200162 is the book category
    }

def calculate_ranking(subject, layer):
    """
    特定科目・レイヤーのレビューデータを元にランキングを算出する。
    戻り値: [{'book_id': id, 'title': title, 'score': score, 'avg_rating': rating, 'review_count': count}, ...]
    """
    # 対象科目の本と全レビューを取得
    books_df = db.get_books_by_subject(subject)
    if books_df.empty:
        return []
        
    all_reviews_df = db.get_reviews_data()
    if all_reviews_df.empty:
        return []
        
    # 指定されたレイヤーと科目に絞り込み
    layer_reviews = all_reviews_df[(all_reviews_df['layer'] == layer) & (all_reviews_df['subject'] == subject)]
    if layer_reviews.empty:
        return []
        
    # 講師の累計レビュー数を取得
    instructor_counts = db.get_instructor_counts()
    
    book_scores = []
    
    # 本ごとにスコアを計算
    for book_id in books_df['book_id']:
        book_reviews = layer_reviews[layer_reviews['book_id'].astype(str) == str(book_id)]
        if book_reviews.empty:
            continue
            
        book_title_values = books_df[books_df['book_id'].astype(str) == str(book_id)]['title'].values
        if len(book_title_values) == 0:
            continue
        book_title = book_title_values[0]
        
        total_weight = 0
        weighted_rating_sum = 0
        
        for _, review in book_reviews.iterrows():
            instructor = review['instructor_name']
            rating = review['rating']
            
            # 講師の重み = numpyのlog10(講師の累計レビュー数 + 10)
            instructor_total_reviews = instructor_counts.get(instructor, 1)
            instructor_weight = np.log10(instructor_total_reviews + 10)
            
            # --- 最終的な重みを計算 ---
            combined_weight = instructor_weight
            
            # (評価値 * 総合重み)
            weighted_rating_sum += rating * combined_weight
            total_weight += combined_weight
            
        if total_weight > 0:
            final_score = weighted_rating_sum / total_weight
            avg_rating = book_reviews['rating'].mean()
            review_count = len(book_reviews)
            
            book_scores.append({
                'book_id': book_id,
                'title': book_title,
                'score': round(float(final_score), 2),
                'avg_rating': round(float(avg_rating), 2),
                'review_count': review_count
            })
            
    # スコアの降順でソート
    book_scores.sort(key=lambda x: x['score'], reverse=True)
    
    return book_scores
