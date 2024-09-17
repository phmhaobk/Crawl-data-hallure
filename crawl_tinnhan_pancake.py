import html
from ketnoisql_server import *
from sqlalchemy import text
import sqlalchemy
from collections import defaultdict
from bs4 import BeautifulSoup
import requests
from api import *
from sqlalchemy.exc import IntegrityError
import time

#crawl_tin_nhan
def clean_html(html_content):
    
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text()

def format_and_group_messages(all_messages, page_id):
    messages_by_date = defaultdict(list)
    
    for message in all_messages:
        
        message_text = message['message'].replace('<div>', '').replace('</div>', '')
        
        if message['from']['id'] == page_id:
            role = "||NV: "
        else:
            role = "||KH: "
        
       
        message_text = clean_html(message_text)
        
        
        message_text = message_text.replace('<br>', '\n')
        message_text = html.unescape(message_text)
        
        
        formatted_message = f"{role}{message_text}-<3-"
        
        
        date_key = message['inserted_at'].split('T')[0]  
        messages_by_date[date_key].append(formatted_message)
    
    
    grouped_messages = []
    for date_key, messages in messages_by_date.items():
        grouped_messages.append({
            'inserted_at': date_key,
            'messages': " ".join(messages)  
        })
    return grouped_messages

def fetch_ids_from_db(view_name):
    with engine.connect() as connection:
        query = text(f"""
            SELECT TOP 2 [id], [customer_id], [page_id], [current_count_message], 
                            [is_got_oldest_Messages], [last_update], [updated_at], [message_count]
            FROM {view_name}
            ORDER BY 
                CASE WHEN phone_number IS NOT NULL THEN 1 ELSE 0 END DESC,
                updated_at DESC
        """)
        df = pd.read_sql(query, connection)
    return df

# WHERE [last_update] IS NULL

def fetch_current_data(schema_name, table_name, conversation_id):
    with engine.connect() as connection:
        query = text(f"""
            SELECT current_count_message, is_got_oldest_Messages
            FROM {schema_name}.{table_name}
            WHERE id = :conversation_id
        """)
        result = connection.execute(query, {'conversation_id': conversation_id}).fetchone()
    return result if result else None


def fetch_message_count(schema_name, table_name, conversation_id):
    with engine.connect() as connection:
        query = text(f"""
            SELECT message_count
            FROM {schema_name}.{table_name}
            WHERE id = :conversation_id
        """)
        result = connection.execute(query, {'conversation_id': conversation_id}).fetchone()
    return result[0] if result else None


def fetch_inserted_at_done(schema_name, table_name, conversation_id):
    with engine.connect() as connection:
        query = text(f"""
            SELECT inserted_at
            FROM {schema_name}.{table_name}
            WHERE conversation_id = :conversation_id
        """)
        result = connection.execute(query, {'conversation_id': conversation_id})
        # Chuyển đổi kết quả thành DataFrame
        df = pd.DataFrame(result.fetchall(), columns=['inserted_at'])
        # Chuyển cột ngày thành định dạng datetime.date
        df['inserted_at'] = pd.to_datetime(df['inserted_at']).dt.date
    return df



def update_conversation(schema_name, table_name, conversation_id, current_count_message):
    
    message_count = fetch_message_count(schema_name, table_name, conversation_id)

    if message_count is None:
        print(f"Conversation ID {conversation_id} not found.")
        return
    
    print(f"Current message_count: {message_count}")

    
    is_got_oldest_Messages = 1 if current_count_message >= int(message_count) else 0

    
    query_update = sa.text(f"""
        UPDATE {schema_name}.{table_name}
        SET current_count_message = :current_count_message,
            is_got_oldest_Messages = :is_got_oldest_Messages
        WHERE id = :conversation_id
    """)

    try:
        with engine.connect() as connection:
            print("Before update:", fetch_current_data(schema_name, table_name, conversation_id))
            result = connection.execute(query_update, {
                'current_count_message': current_count_message,
                'is_got_oldest_Messages': is_got_oldest_Messages,
                'conversation_id': conversation_id
            })
            connection.commit()
            print("Updated rows:", result.rowcount)
            print("After update:", fetch_current_data(schema_name, table_name, conversation_id))
    except Exception as e:
        print(f"Error updating conversation: {e}")

    print(f"Updated conversation {conversation_id} with current_count_message={current_count_message} and is_got_oldest_Messages={is_got_oldest_Messages}")

'''   
def fetch_messages_for_conversation(page_id, customer_id, conversation_id):
    access_token = page_access_tokens.get(page_id)
    if not access_token:
        return []
    
    url_messages = f'https://pages.fm/api/public_api/v1/pages/{page_id}/conversations/{conversation_id}/messages'
    all_messages = []
    current_count = 0
    
    while True:
        params = {
            'page_access_token': access_token,
            'customer_id': customer_id,
            'current_count': current_count
        }
        
        response = requests.get(url_messages, params=params)
        if response.status_code == 200:
            json_response = response.json()
            if 'messages' in json_response:
                messages_data = json_response['messages']
                if not messages_data:
                    break
                all_messages.extend(messages_data)
                current_count += len(messages_data)
                print(f"Fetched {len(messages_data)} messages. Current count: {current_count}")
            else:
                break
        elif response.status_code == 429:
            print("Rate limit exceeded. Waiting for 60 seconds...")
            time.sleep(60)  
        else:
            print(f"Failed to fetch messages. Status code: {response.status_code}")
            break
    
    return {
        'conversation_id': conversation_id,
        'customer_id': customer_id,
        'messages': all_messages,
        'page_id': page_id,
        'current_count_message': current_count
    }    
'''
import requests
import time

def fetch_messages_for_conversation(page_id, customer_id, conversation_id, total_message):
    access_token = page_access_tokens.get(page_id)
    if not access_token:
        return []
    
    url_messages = f'https://pages.fm/api/public_api/v1/pages/{page_id}/conversations/{conversation_id}/messages'
    all_messages = []
    current_count = 0
    
    while current_count < total_message:
        params = {
            'page_access_token': access_token,
            'customer_id': customer_id,
            'current_count': current_count
        }
        
        response = requests.get(url_messages, params=params)
        if response.status_code == 200:
            json_response = response.json()
            if 'messages' in json_response:
                messages_data = json_response['messages']
                if not messages_data:
                    break
                all_messages.extend(messages_data)
                current_count += len(messages_data)
                print(f"Fetched {len(messages_data)} messages. Current count: {current_count}")
            else:
                break
        elif response.status_code == 429:
            print("Rate limit exceeded. Waiting for 60 seconds...")
            time.sleep(5)
        else:
            print(f"Failed to fetch messages. Status code: {response.status_code}")
            break
    
    if current_count < total_message:
        print(f"Warning: Only {current_count} out of {total_message} messages were fetched.")

    return {
        'conversation_id': conversation_id,
        'customer_id': customer_id,
        'messages': all_messages,
        'page_id': page_id,
        'current_count_message': current_count
    }

