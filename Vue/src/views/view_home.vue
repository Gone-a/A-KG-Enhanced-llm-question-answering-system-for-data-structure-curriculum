<template>
  <div class="home-page">
    <!-- 对话列表侧边栏（左侧） -->
    <div class="chat-sidebar">
      <!-- 新建对话按钮 -->
      <button class="new-chat-btn" @click="addNewChat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/>
        </svg>
        <span>新建对话</span>
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
          <div class="chat-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" fill="currentColor"/>
            </svg>
          </div>
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
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor"/>
            </svg>
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
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
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
    radial-gradient(circle at 20% 80%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 40% 40%, rgba(6, 182, 212, 0.06) 0%, transparent 50%);
  pointer-events: none;
}

/* 左侧对话列表样式 - 现代化玻璃态效果 */
.chat-sidebar {
  width: 280px;
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(226, 232, 240, 0.6);
  display: flex;
  flex-direction: column;
  box-shadow: 
    0 4px 20px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.4);
  z-index: 10;
  margin: 0;
  padding: 0;
  position: relative;
}

/* 新建对话按钮 - 现代化设计 */
.new-chat-btn {
  margin: 20px 16px 16px 16px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 
    0 2px 8px rgba(99, 102, 241, 0.2),
    0 1px 3px rgba(0, 0, 0, 0.1);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.new-chat-btn:hover {
  transform: translateY(-2px);
  box-shadow: 
    0 4px 16px rgba(99, 102, 241, 0.3),
    0 2px 6px rgba(0, 0, 0, 0.15);
}

.new-chat-btn:active {
  transform: translateY(0);
}

/* 对话列表容器 */
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 16px 8px;
}

/* 对话项样式 */
.chat-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  margin: 4px 8px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: rgba(248, 250, 252, 0.6);
  border: 1px solid rgba(226, 232, 240, 0.4);
  position: relative;
  overflow: hidden;
  gap: 12px;
}

.chat-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6366f1;
  font-size: 14px;
  flex-shrink: 0;
  transition: all 0.3s ease;
}

.chat-icon svg {
  width: 16px;
  height: 16px;
  color: #6b7280;
  transition: color 0.2s ease;
}

.chat-item.active .chat-icon {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.chat-item.active .chat-icon svg {
  color: #6366f1;
}

.chat-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.chat-item:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(99, 102, 241, 0.2);
  transform: translateX(4px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.chat-item:hover::before {
  opacity: 1;
}

.chat-item.active {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  border-color: rgba(255, 255, 255, 0.2);
  box-shadow: 
    0 2px 8px rgba(99, 102, 241, 0.3),
    0 1px 3px rgba(0, 0, 0, 0.1);
}

.chat-item.active::before {
  opacity: 0;
}

.chat-item-content {
  flex: 1;
  min-width: 0;
}

.chat-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
  color: inherit;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.chat-preview {
  font-size: 12px;
  color: #64748b;
  opacity: 0.8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-item.active .chat-preview {
  color: rgba(255, 255, 255, 0.8);
}

.delete-btn {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.2s ease;
  opacity: 0;
  transform: scale(0.8);
}

.chat-item:hover .delete-btn {
  opacity: 1;
  transform: scale(1);
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.chat-item.active .delete-btn {
  color: rgba(255, 255, 255, 0.7);
}

.chat-item.active .delete-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

/* 中间图谱容器 */
.graph-container {
  flex: 1;
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-right: 1px solid rgba(226, 232, 240, 0.6);
  position: relative;
  overflow: hidden;
  min-width: 0; /* 确保flex容器能够正确收缩 */
}

/* 右侧聊天容器 - 调整为占至少五分之二的面积 */
.chat-main {
  width: 42%; /* 设置为42%，确保至少占五分之二（40%）的面积 */
  min-width: 480px; /* 设置最小宽度，确保在小屏幕上仍有良好体验 */
  max-width: 50%; /* 设置最大宽度，避免占用过多空间 */
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  position: relative;
}
</style>