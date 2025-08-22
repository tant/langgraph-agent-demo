#!/bin/bash

# Script đơn giản để tạo một cuộc trò chuyện và gửi tin nhắn đến API.
#
# Yêu cầu:
# - curl: Thường được cài đặt sẵn trên hầu hết các hệ thống.
# - jq: Công cụ xử lý JSON trên dòng lệnh. Cài đặt bằng 'sudo apt-get install jq' hoặc 'brew install jq'.

# --- Cấu hình ---
BASE_URL="http://localhost:8000"
API_KEY="default-dev-key"
USER_ID="script-user-$(date +%s)" # Tạo user_id duy nhất cho mỗi lần chạy
MESSAGE_CONTENT=${1:-"Xin chào từ script!"} # Lấy nội dung tin nhắn từ tham số đầu tiên, hoặc dùng giá trị mặc định

# --- Bước 1: Tạo cuộc trò chuyện mới ---
echo "Đang tạo cuộc trò chuyện mới cho user: $USER_ID..."

# Dùng curl để gửi yêu cầu và lưu lại phản hồi
response=$(curl -s -X POST "$BASE_URL/conversations" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"user_id\": \"$USER_ID\"}")

# Kiểm tra xem yêu cầu có thành công không bằng cách kiểm tra nội dung phản hồi
if ! echo "$response" | jq -e '.id' > /dev/null; then
    echo "Lỗi: Không thể tạo cuộc trò chuyện."
    echo "Phản hồi từ server: $response"
    exit 1
fi

# Trích xuất conversation ID bằng jq
conversation_id=$(echo "$response" | jq -r '.id')
echo "Tạo cuộc trò chuyện thành công. ID: $conversation_id"
echo ""


# --- Bước 2: Gửi tin nhắn đến cuộc trò chuyện mới ---
echo "Đang gửi tin nhắn đến conversation ID: $conversation_id..."
echo "Nội dung: \"$MESSAGE_CONTENT\""

send_message_response=$(curl -s -X POST "$BASE_URL/conversations/$conversation_id/messages" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"content\": \"$MESSAGE_CONTENT\"}")

# Kiểm tra xem tin nhắn đã được chấp nhận chưa
if ! echo "$send_message_response" | jq -e '.status == "accepted"' > /dev/null; then
    echo "Lỗi: Không thể gửi tin nhắn."
    echo "Phản hồi từ server: $send_message_response"
    exit 1
fi

message_id=$(echo "$send_message_response" | jq -r '.message_id')
echo "Đã gửi tin nhắn thành công và được server chấp nhận."
echo "Message ID: $message_id"
echo ""


# --- Bước 3: Gợi ý bước tiếp theo ---
echo "Trợ lý ảo đang xử lý tin nhắn trong nền."
echo "Để kiểm tra câu trả lời, hãy chạy lệnh sau sau vài giây:"
echo "curl -X GET \"$BASE_URL/conversations/$conversation_id/history\" -H \"X-API-Key: $API_KEY\" | jq"
