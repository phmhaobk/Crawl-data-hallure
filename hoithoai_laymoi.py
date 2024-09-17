from datetime import datetime, timedelta
import pandas as pd
from crawl_hoithoai_pancake import *
from api import *
from ketnoisql_server import *
import logging

logging.basicConfig(level=logging.INFO,  
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler('update_progress_hoi_thoai.log'),
                        logging.StreamHandler()
                    ])


logger = logging.getLogger()



all_conversations_data = []
log_data_list = []


def insert_log_data(log_entries, schema_name, table_name):
    with engine.connect() as connection:
        with connection.begin():
            # Define the insert statement
            insert_statement = sqlalchemy.text(f"""
                INSERT INTO {schema_name}.{table_name} 
                (logDate, databaseName, tableName, status, fromDate, toDate, Record, description) 
                VALUES (:logDate, :databaseName, :tableName, :status, :fromDate, :toDate, :Record, :description)
            """)

            # Execute the insert statement with the log entries
            connection.execute(insert_statement, log_entries)
            logger.info(f"Inserted {len(log_entries)} log entries into the database.")

def process_conversations():
    if not df_hoithoai.empty:
        df_hoithoai['phone_number'] = df_hoithoai['recent_phone_numbers'].apply(extract_phone_number)
        df_hoithoai['customer_fb_id'] = df_hoithoai['customers'].apply(extract_customers_fb_id)
        df_hoithoai['customer_name'] = df_hoithoai['customers'].apply(extract_customers_name)
        df_hoithoai['inserted_at'] = df_hoithoai['inserted_at'].apply(convert_to_date)
        df_hoithoai['updated_at'] = df_hoithoai['updated_at'].apply(convert_to_date)
        df_hoithoai['tags_id'] = df_hoithoai['tags'].apply(extract_tags_id)
        df_hoithoai['tag_histories_id'] = df_hoithoai['tag_histories'].apply(extract_tag_histories_id)
        df_hoithoai['assign_user_id'] = df_hoithoai['current_assign_users'].apply(extract_assign_user_fb_id)
        df_hoithoai['tags_text'] = df_hoithoai['tags'].apply(extract_tags_text)

        logger.info(f'Processed DataFrame with columns: {df_hoithoai.columns.tolist()}')
        
        df_hoithoai['tags_id'] = df_hoithoai['tags_id'].apply(lambda x: ','.join(map(str, x)) if x else None)
        
        total_inserted = 0
        total_updated = 0

        for index, row in df_hoithoai.iterrows():
            conversation_data = {
                'page_id': row.get('page_id', ''),
                'post_id': row.get('post_id', ''),
                'id': row.get('id', ''),
                'assign_user_id': row.get('assign_user_id', None) if row.get('assign_user_id') else None,
                'customer_id': row.get('customer_id', ''),
                'customer_fb_id': row.get('customer_fb_id', ''),
                'has_phone': row.get('has_phone', ''),
                'inserted_at': row.get('inserted_at', ''),
                'updated_at': row.get('updated_at', ''),
                'message_count': row.get('message_count', ''),
                'tags_id': row.get('tags_id', None) if row.get('tags_id') else None,
                'tag_histories_id': row.get('tag_histories_id', ''),
                'type': row.get('type', ''),
                'phone_number': row.get('phone_number', None) if row.get('phone_number') else None,
                'customer_name': row.get('customer_name'),
                'current_count_message': '',  
                'is_got_oldest_Messages': row.get('is_got_oldest_Messages', False),
                'tags_text': row.get('tags_text')
            }
            
            if conversation_exists(conversation_data['id'], schema_name_conversations, table_name_conversations):
                update_conversation(conversation_data, schema_name_conversations, table_name_conversations)
                total_updated += 1
            else:
                insert_conversations([conversation_data], schema_name_conversations, table_name_conversations)
                
                total_inserted += 1

        log_data_list = []

        if total_updated > 0:
            log_data_list.append({
                "logDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "databaseName": "stg",
                "tableName": "pancake_gd_HoiThoai",
                "status": "Success",
                "fromDate": current_start_time.strftime("%Y-%m-%d"),
                "toDate": current_end_time.strftime("%Y-%m-%d"),
                "Record": total_updated,
                "description": f"Update success page {page_id} {total_updated} into table pancake_gd_HoiThoai of stg"
            })

           
        if total_inserted > 0:
            log_data_list.append({
                "logDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "databaseName": "stg",
                "tableName": "pancake_gd_HoiThoai",
                "status": "Success",
                "fromDate": current_start_time.strftime("%Y-%m-%d"),
                "toDate": current_end_time.strftime("%Y-%m-%d"),
                "Record": total_inserted,
                "description": f"Insert success page {page_id} {total_inserted} into table pancake_gd_HoiThoai of stg"
            })
            
        if log_data_list:  
            insert_log_data(log_data_list, "stg", "Log_HoiThoai")
            for entry in log_data_list:
                logger.info(entry)
            log_data_list.clear()  


#start_time = datetime(2024, 8, 20)  
#end_time = datetime(2024, 8, 20, 23, 59, 59)  

# Lấy ngày hôm nay
today = datetime.today()

# Lấy ngày hôm qua bằng cách trừ đi 1 ngày từ hôm nay
yesterday = today - timedelta(days=1)

# Đặt thời gian bắt đầu và kết thúc cho ngày hôm qua
start_time = datetime(yesterday.year, yesterday.month, yesterday.day)
end_time = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)

current_start_time = start_time

while current_start_time < end_time:
    # Tính toán current_end_time cho 10 ngày tiếp theo
    current_end_time = current_start_time + timedelta(days=10) - timedelta(seconds=1)
    
    # Đảm bảo current_end_time không vượt quá end_time
    current_end_time = min(current_end_time, end_time)

    since_time = int(current_start_time.timestamp())
    until_time = int(current_end_time.timestamp())

    # Lặp qua từng page_id để lấy dữ liệu hội thoại
    for page_id in page_ids:
        access_token = page_access_tokens.get(page_id)
        if access_token:
            logger.info(f'Fetching conversations for page_id: {page_id} from {current_start_time} to {current_end_time}')
            conversations = fetch_conversations(page_id, access_token, since_time, until_time)
            if conversations:
                all_conversations_data.extend(conversations)
                logger.info(f'Fetched {len(conversations)} conversations for page_id: {page_id}')
                
                df_hoithoai = pd.DataFrame(all_conversations_data)
                logger.info(f'DataFrame created with shape: {df_hoithoai.shape}')

                process_conversations()

    # Cập nhật current_start_time để lấy dữ liệu 10 ngày tiếp theo
    current_start_time = current_end_time + timedelta(seconds=1)
