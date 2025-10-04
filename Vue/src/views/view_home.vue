<template>
  <div class="home-page">
    <!-- 对话列表侧边栏（左侧） -->
    <div class="chat-sidebar">
      <!-- 新建对话按钮 -->
      <button class="new-chat-btn" @click="chatStore.createNewChat">
        <i class="fas fa-plus"></i> 新建对话
      </button>
      
      <!-- 对话列表 -->
      <div class="chat-list">
        <div 
          class="chat-item" 
          v-for="(chat, index) in chatStore.chatHistories" 
          :key="chat.id"
          :class="{ active: index === chatStore.currentChatIndex }"
          @click="chatStore.switchChat(index)"
        >
          <div class="chat-item-content">
            <div class="chat-title">{{ chat.title }}</div>
            <div class="chat-preview">
              {{ chat.messages.length > 0 
                ? (chat.messages[chat.messages.length - 1].text.length > 20 
                  ? chat.messages[chat.messages.length - 1].text.slice(0, 20) + '...' 
                  : chat.messages[chat.messages.length - 1].text) 
                : '暂无消息' }}
            </div>
          </div>
          <button class="delete-btn" @click.stop="chatStore.deleteChat(index)">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- 图片窗口（中间）-->
    <div class="graph-container">
      <graphBox :graph-data="chatStore.currentChat.graph" />
    </div>
    
    <!-- 聊天窗口（右侧） -->
    <div class="chat-main">
      <chatBox 
        :messages="chatStore.currentChat.messages" 
        @messageAdded="chatStore.handleMessageAdded"
        @clearChat="chatStore.clearCurrentChat"
        @graphAdded="chatStore.graphshow"
      />
    </div>
  </div>
</template>

<script setup>
import { useChatStore } from '../store/dataStore.js'
import chatBox from "../components/chatBox.vue";
import graphBox from "../components/graphBox.vue";

const chatStore = useChatStore();

// // 图片数据
// const myGraphData = ref({
//   nodes: [
//     { id: 1, name: "产品部" },
//     { id: 2, name: "技术部" },
//     { id: 3, name: "设计部" },
//     { id: 4, name: "市场部" },
//     { id: 5, name: "财务部" },
//     { id: 6, name: "人力资源部" },
//     { id: 7, name: "客服部" }
//   ],
//   links: [
//     { source: 1, target: 2, relation: "关系1"},
//     { source: 1, target: 3, relation: "关系2"},
//     { source: 2, target: 3, relation: "关系3"},
//     { source: 1, target: 4, relation: "关系4"},
//     { source: 4, target: 7, relation: "关系5"},
//     { source: 2, target: 5, relation: "关系6"},
//     { source: 3, target: 5, relation: "关系7"},
//     { source: 5, target: 6, relation: "关系8"},
//     { source: 6, target: 2, relation: "关系9"},
//     { source: 6, target: 3, relation: "关系10"}
//   ]
// });

// const chatHistories = ref([
//   { id: Date.now(), title: '新对话', messages: [], graph:myGraphData }
// ]);
// const currentChatIndex = ref(0);

// const currentChat = computed(() => chatHistories.value[currentChatIndex.value]);

// const createNewChat = () => {
//   const newChat = {
//     id: Date.now(),
//     title: '新对话',
//     messages: [],
//     graph:{}
//   };
//   chatHistories.value.push(newChat);
//   currentChatIndex.value = chatHistories.value.length - 1;
// };

// const switchChat = (index) => {
//   currentChatIndex.value = index;
//   axios.post("http://localhost:5000/switchChat",currentChat.value.messages)
//     .then(response => {
//       console.log(currentChat.value.messages);
//       console.log(response.data);
//     })
//     .catch(error => {
//       console.log(currentChat.value.messages);
//       console.error("请求出错：", error);
//     })
// };

// const handleMessageAdded = (newMessage) => {
//   currentChat.value.messages.push(newMessage);
//   if (currentChat.value.messages.length === 1) {
//     currentChat.value.title = newMessage.text.slice(0, 10) || '新对话';
//   }
// };

// const clearCurrentChat = () => {
//   currentChat.value.messages = [];
// };

// const graphshow = (graphdata) =>{
//   console.log("已传入");
//   console.log(graphdata);
//   if (graphdata?.nodes && graphdata?.links) {
//     // 整体替换为新对象（触发子组件 props 引用变化）
//     currentChat.value.graph = { ...graphdata }; 
//     console.log("图形数据更新成功", graphdata);
//   } else {
//     console.error("无效的图形数据格式", graphdata);
//   }
// };

// // 新增删除对话方法
// const deleteChat = (index) => {
//   if (chatHistories.value.length <= 1) {
//     currentChat.value.messages = [];
//     currentChat.value.title = '新对话';
//     return;
//   }
//   chatHistories.value.splice(index, 1);
//   currentChatIndex.value = Math.max(0, currentChatIndex.value > index ? currentChatIndex.value - 1 : 0);
// };
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: row;
  width: 100%;
  min-width: 1600px;
  height: 85svh;
  overflow: hidden;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  position: relative;
}

.home-page::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(255, 119, 198, 0.15) 0%, transparent 50%),
    radial-gradient(circle at 40% 40%, rgba(120, 219, 255, 0.1) 0%, transparent 50%);
  pointer-events: none;
}

/* 左侧对话列表样式 - 现代化玻璃态效果 */
.chat-sidebar {
  width: 280px;
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  flex-direction: column;
  box-shadow: 
    0 8px 32px rgba(0, 0, 0, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  z-index: 10;
  margin: 0;
  padding: 0;
  position: relative;
}

/* 新建对话按钮 - 现代化设计 */
.new-chat-btn {
  margin: 20px 16px 16px 16px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 
    0 4px 15px rgba(102, 126, 234, 0.4),
    0 2px 4px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow: hidden;
}

.new-chat-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.new-chat-btn::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  transition: width 0.3s ease, height 0.3s ease;
}

.new-chat-btn:hover {
  transform: translateY(-2px);
  box-shadow: 
    0 8px 25px rgba(102, 126, 234, 0.5),
    0 4px 8px rgba(0, 0, 0, 0.15);
}

.new-chat-btn:hover::before {
  left: 100%;
}

.new-chat-btn:active {
  transform: translateY(-1px) scale(0.98);
  transition: all 0.1s;
}

.new-chat-btn:active::after {
  width: 120px;
  height: 120px;
}

.new-chat-btn i {
  font-size: 16px;
  transition: transform 0.3s;
}

.new-chat-btn:hover i {
  transform: rotate(90deg);
}

/* 对话列表容器 */
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 16px 8px;
}

.chat-list::-webkit-scrollbar {
  width: 6px;
}

.chat-list::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 3px;
}

.chat-list::-webkit-scrollbar-thumb {
  background: rgba(102, 126, 234, 0.3);
  border-radius: 3px;
  transition: background 0.3s;
}

.chat-list::-webkit-scrollbar-thumb:hover {
  background: rgba(102, 126, 234, 0.5);
}

/* 单个对话项样式 - 现代化卡片设计 */
.chat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 12px;
  margin: 4px 0;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-left: 3px solid transparent;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(10px);
  position: relative;
  overflow: hidden;
}

.chat-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  opacity: 0;
  transition: opacity 0.3s;
}

.chat-item:hover {
  transform: translateX(4px);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 
    0 4px 20px rgba(0, 0, 0, 0.1),
    0 2px 4px rgba(0, 0, 0, 0.05);
}

.chat-item:hover::before {
  opacity: 1;
}

.chat-item.active {
  background: rgba(102, 126, 234, 0.15);
  border-left-color: #667eea;
  transform: translateX(6px);
  box-shadow: 
    0 6px 25px rgba(102, 126, 234, 0.2),
    0 3px 6px rgba(0, 0, 0, 0.1);
}

.chat-item.active::before {
  opacity: 1;
}

/* 对话项内容 */
.chat-item-content {
  flex: 1;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.chat-title {
  font-size: 14px;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.3s;
}

.chat-item.active .chat-title {
  color: #667eea;
}

.chat-preview {
  font-size: 12px;
  color: #718096;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

/* 删除按钮 - 现代化设计 */
.delete-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.1);
  border: none;
  color: #ef4444;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  transform: scale(0.8);
  position: relative;
  z-index: 2;
  overflow: hidden;
}

.delete-btn::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  background: rgba(255, 255, 255, 0.4);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  transition: width 0.3s ease, height 0.3s ease;
}

.chat-item:hover .delete-btn {
  opacity: 1;
  transform: scale(1);
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
}

.delete-btn:active {
  transform: scale(0.95);
}

.delete-btn:active::before {
  width: 40px;
  height: 40px;
}

/* 中间可视化区域样式 - 现代化玻璃态 */
.graph-container {
  flex: 1;
  height: 100%;
  padding: 20px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(255, 255, 255, 0.2);
  position: relative;
}

.graph-container::before {
  content: '';
  position: absolute;
  top: 20px;
  left: 20px;
  right: 20px;
  bottom: 20px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  pointer-events: none;
}

/* 右侧聊天区域 - 现代化设计 */
.chat-main {
  width: 800px;
  max-width: calc(100% - 240px);
  margin-left: auto;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-left: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 
    -8px 0 32px rgba(0, 0, 0, 0.1),
    inset 1px 0 0 rgba(255, 255, 255, 0.2);
}

/* 响应式适配调整 */
@media (max-width: 768px) {
  .home-page {
    flex-direction: column;
    background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
  }
  
  .chat-sidebar {
    width: 100%;
    height: 40%;
    border-right: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  }
  
  .chat-main {
    width: 100%;
    max-width: 100%;
    height: 60%;
    border-left: none;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
  }
  
  .graph-container {
    display: none;
  }
}

/* 添加一些微妙的动画效果 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-item {
  animation: fadeInUp 0.3s ease-out;
}

.chat-item:nth-child(1) { animation-delay: 0.1s; }
.chat-item:nth-child(2) { animation-delay: 0.2s; }
.chat-item:nth-child(3) { animation-delay: 0.3s; }
.chat-item:nth-child(4) { animation-delay: 0.4s; }
.chat-item:nth-child(5) { animation-delay: 0.5s; }
</style>