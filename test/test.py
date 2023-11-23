# import socket
#
# # 创建UDP socket对象
# udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#
# # 绑定服务器地址和端口
# server_address = ('127.0.0.1', 12345)
# udp_socket.bind(server_address)
#
# # 循环接收数据
# while True:
#     print("等待接收数据...")
#     data, client_address = udp_socket.recvfrom(1024)  # 最大接收字节数为1024
#     print(f"从 {client_address} 接收到消息：{data.decode('utf-8')}")
#
# # 关闭socket（实际应用中不会运行到这里，需要通过其他方式退出循环）
# # udp_socket.close()


def tup(item, ret_is_single=False):
    """Forces casting of item to a tuple (for a list) or generates a
    single element tuple (for anything else)"""
    if hasattr(item, '__iter__'):
        return (item,) if ret_is_single else item
    else:
        return ((item,),) if ret_is_single else (item,)


# Usage examples
my_list = [1, 2, 3]
converted_list = tup(my_list)
print(converted_list)  # Output: [1, 2, 3]

single_item = 5
converted_single = tup(single_item)
print(converted_single)  # Output: (5,)

my_string = "Hello"
converted_string = tup(my_string)
print(converted_string)  # Output: 'Hello'

single_as_tuple = tup(10, ret_is_single=True)
print(single_as_tuple)  # Output: (10,)
