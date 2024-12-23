import json
from zlapi import ZaloAPI, ZaloAPIException
from zlapi.models import *
from colorama import Fore, Style, init
# Initialize colorama
init(autoreset=True)
class CustomClient(ZaloAPI):
    def __init__(self, api_key, secret_key, imei, session_cookies):
        super().__init__(api_key, secret_key, imei=imei, session_cookies=session_cookies)
        self.excluded_user_ids = ['791631427531882541']
        self.data_file = 'user_data.json'
        self.message_counts = {}  # Track message counts
        self.load_data()

    def load_data(self):
        """Load user data and message counts from a JSON file."""
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.user_data = data.get('user_data', {})
                self.message_counts = data.get('message_counts', {})
        except FileNotFoundError:
            self.user_data = {}
            self.message_counts = {}
        except json.JSONDecodeError:
            self.user_data = {}
            self.message_counts = {}

    def save_data(self):
        """Save user data and message counts to a JSON file."""
        with open(self.data_file, 'w') as f:
            json.dump({'user_data': self.user_data, 'message_counts': self.message_counts}, f, indent=4)

    def get_user_data(self, user_id):
        """Get user data for a specific user ID, initializing if not present."""
        if user_id not in self.user_data:
            self.user_data[user_id] = {'balance': 0, 'wins': 0, 'losses': 0}
        return self.user_data[user_id]

    def update_message_count(self, thread_id, author_id):
        """Update message count for a specific thread and author."""
        if thread_id not in self.message_counts:
            self.message_counts[thread_id] = {}
        if author_id not in self.message_counts[thread_id]:
            self.message_counts[thread_id][author_id] = 0
        self.message_counts[thread_id][author_id] += 1

    def fetchUserInfo(self, userId):
        """Fetch user info and return zaloName or displayName."""
        try:
            user_info = super().fetchUserInfo(userId)
            print(f"Fetched user info for {userId}: {user_info}")  # Debug print

            if 'changed_profiles' in user_info and userId in user_info['changed_profiles']:
                zalo_name = user_info['changed_profiles'][userId].get('zaloName', None)
                if zalo_name:
                    return zalo_name
                else:
                    display_name = user_info['changed_profiles'][userId].get('displayName', userId)
                    return display_name
            else:
                return userId

        except Exception as e:
            print(f"{Fore.RED}Error fetching user info: {e}")
            return userId  # Return userId if there is an error

    def is_admin(self, thread_id, user_id):
        """Check if a user is an admin in a specific thread."""
        try:
            group_info = self.fetchGroupInfo(groupId=thread_id)
            print(group_info)
            admin_ids = group_info.gridInfoMap[thread_id]['adminIds']
            creator_id = group_info.gridInfoMap[thread_id]['creatorId']
            print(admin_ids)
            return user_id in admin_ids or user_id == creator_id
        except ZaloAPIException as e:
            print(f"{Fore.RED}Error checking admin status: {e}")
            return False

    def handle_count(self, message_object, thread_id, author_id):
        """Handle the /count command to list message counts per user in a thread."""
        if hasattr(message_object, 'content') and isinstance(message_object.content, str):
            if message_object.content.startswith('/count'):
                try:
                    if thread_id not in self.message_counts:
                        self.message_counts[thread_id] = {}

                    counts = self.message_counts[thread_id]
                    if not counts:
                        response = "Chưa có tin nhắn nào trong nhóm này."
                    else:
                        sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]
                        response = "Top 10 người gửi tin nhắn nhiều nhất:\n"
                        for user_id, count in sorted_counts:
                            display_name = self.fetchUserInfo(userId=user_id)
                            response += f"{display_name} ({user_id}): {count} tin nhắn\n"

                    self.send(
                        Message(text=response),
                        thread_id=thread_id,
                        thread_type=ThreadType.GROUP
                    )

                    self.save_data()

                except Exception as e:
                    self.send(
                        Message(text="Đã xảy ra lỗi trong khi xử lý lệnh của bạn."),
                        thread_id=thread_id,
                        thread_type=ThreadType.GROUP
                    )
                    print(f"{Fore.RED}Error handling /count command: {e}")

    def handle_kick(self, message_object, thread_id, author_id):
        """Handle the /kick command to remove a user from the group."""
        if hasattr(message_object, 'content') and isinstance(message_object.content, str):
            if message_object.content.startswith('/kick '):
                try:
                    if self.is_admin(thread_id, author_id):
                        if 'mentions' in message_object and message_object.mentions:
                            mentioned_user_id = message_object.mentions[0]['uid']
                            if mentioned_user_id not in self.excluded_user_ids:
                                try:
                                    self.kickUsersFromGroup([mentioned_user_id], thread_id)
                                    self.send(
                                        Message(text="Người dùng đã bị đuổi khỏi nhóm."),
                                        thread_id=thread_id,
                                        thread_type=ThreadType.GROUP,
                                        mark_message="urgent"
                                    )
                                except ZaloAPIException as e:
                                    self.send(
                                        Message(text="Không thể đuổi người dùng."),
                                        thread_id=thread_id,
                                        thread_type=ThreadType.GROUP
                                    )
                            else:
                                self.send(
                                    Message(text="Không thể đuổi người dùng đã chỉ định."),
                                    thread_id=thread_id,
                                    thread_type=ThreadType.GROUP
                                )
                        else:
                            self.send(
                                Message(text="Không có người dùng nào được đề cập."),
                                thread_id=thread_id,
                                thread_type=ThreadType.GROUP
                            )
                    else:
                        self.send(
                            Message(text="Bạn không có quyền sử dụng lệnh này."),
                            thread_id=thread_id,
                            thread_type=ThreadType.GROUP
                        )
                except Exception as e:
                    self.send(
                        Message(text="Đã xảy ra lỗi khi xử lý lệnh /kick."),
                        thread_id=thread_id,
                        thread_type=ThreadType.GROUP
                    )
                    print(f"{Fore.RED}Error handling /kick command: {e}")

    def onMessage(self, mid, author_id, message, message_object, thread_id, thread_type):
        """Process incoming messages and handle commands."""
        print(f"{Fore.GREEN}THÔNG BÁO TIN NHẮN\n"
              "------------------------------\n"
              f"TÊN:@Tten nguoi gui\n"
              f"TIN NHẮN: {Style.BRIGHT}{message} {Style.NORMAL}\n"
              f"ID NGƯỜI GỬI: {Fore.CYAN}{author_id} {Style.NORMAL}\n"
              f"ID: {Fore.YELLOW}{thread_id}\n"
              f"LOẠI: {Fore.BLUE}{thread_type}\n"
              f"{Fore.GREEN}------------------------------\n"
              )

        try:
            self.update_message_count(thread_id, author_id)

            self.handle_kick(message_object, thread_id, author_id)

            self.handle_count(message_object, thread_id, author_id)
                
        except Exception as ex:
            print(f"{Fore.RED}Error processing message: {ex}")

imei = "4f7dfb7d-7666-448a-b5e6-5728699b0b2f-b78b4e2d6c0a362c418b145fe44ed73f"
session_cookies = {"_ga":"GA1.2.237177959.1734676434","_ga_VM4ZJE1265":"GS1.2.1734676435.1.0.1734676435.0.0.0","_ga_RYD7END4JE":"GS1.2.1734676439.1.1.1734676440.59.0.0","_zlang":"vn","_gid":"GA1.2.1586626960.1734871183","__zi":"3000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjIXe9fEM8Wyd-wdc4jPWd2TwwtGJ5c7S9_eg3an.1","__zi-legacy":"3000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjIXe9fEM8Wyd-wdc4jPWd2TwwtGJ5c7S9_eg3an.1","ozi":"2000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjMXe9fFM8yxdkMhbqXIX3MRgwcMJng3DPwhgvLA5uO.1","app.event.zalo.me":"7280909900899205763","zpsid":"_xEB.426330329.12.WlZdjEoAiS0rmjZPu8gnm9dvm_JUl8BptBc3-PZgJ6JVPEbTxRYigOkAiS0","zpw_sek":"SMEw.426330329.a0.d1xHI59i3pgB96OZSsmFEYbEQb5mLYrSPpziTnmzMLu-A3vR01GzSmeZUNqrKJ8OBnXln_PVuMBFRJidEmiFEW"}

client = CustomClient('api_key', 'secret_key', imei=imei, session_cookies=session_cookies)
client.listen()