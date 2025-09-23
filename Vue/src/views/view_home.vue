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
  /* 改为横向布局 */
  flex-direction: row;
  width: 100%;
  /* 移除最小宽度限制，让布局更灵活 */
  min-width: 1600px;
  height: 85svh; /* 使用全屏高度 */
  overflow: hidden;
  background-color: #f5f7fa;
}

/* 左侧对话列表样式 - 紧贴左侧 */
.chat-sidebar {
  width: 280px;
  height: 100%;
  background-color: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.03);
  z-index: 10;
  /* 确保紧贴左侧 */
  margin: 0;
  padding: 0;
}

/* 新建对话按钮 */
.new-chat-btn {
  margin: 16px;
  padding: 10px 16px;
  background-color: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.new-chat-btn:hover {
  background-color: #2563eb;
  transform: translateY(-1px);
}

.new-chat-btn:active {
  transform: translateY(0);
}

/* 对话列表容器 */
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 16px;
}

/* 单个对话项样式 */
.chat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-left: 3px solid transparent;
}

.chat-item:hover {
  background-color: #f1f5f9;
}

.chat-item.active {
  background-color: #eff6ff;
  border-left-color: #3b82f6; /* 活跃状态左侧蓝色标识 */
}

/* 对话项内容 */
.chat-item-content {
  flex: 1;
  overflow: hidden;
}

.chat-title {
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-preview {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 删除按钮 */
.delete-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0;
}

.chat-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background-color: #fee2e2;
  color: #ef4444;
}

/* 中间可视化区域样式 - 确保足够空间 */
.graph-container {
  flex: 1; /* 占据父级flex布局的剩余全部空间 */
  height: 100%;
  padding: 20px;
  box-sizing: border-box;
  display: flex;      /* 开启flex布局，用于内部元素居中 */
  align-items: center;/* 垂直居中 */
  justify-content: center; /* 水平居中 */
  background-color: #ffffff;
  border-right: 1px solid #e2e8f0;
}

.chat-main {
  /* 固定右侧位置，左侧收缩 */
  width: 800px; /* 收缩后的宽度 */
  max-width: calc(100% - 240px); /* 确保不超过可用空间 */
  margin-left: auto; /* 靠右对齐，右侧不挪动 */
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
  border-left: 1px solid #e2e8f0; /* 左侧边框，增强视觉分隔 */
}

/* 响应式适配调整 */
@media (max-width: 768px) {
  .home-page {
    flex-direction: column;
  }
  
  .chat-sidebar {
    width: 100%;
    height: 40%;
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
  }
  
  .chat-main {
    height: 60%;
  }
}
</style>