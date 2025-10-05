<template>
  <div class="chat-container">
    <!-- 页面标题区域 -->
    <header class="chat-header">
      <div class="logo">
        <svg width="32" height="32" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
          <!-- 外圆环 -->
          <circle cx="50" cy="50" r="45" stroke="#6366f1" stroke-width="3" fill="none" opacity="0.3"/>
          <!-- 内圆 -->
          <circle cx="50" cy="50" r="35" fill="#6366f1" opacity="0.1"/>
          <!-- 中心节点 -->
          <circle cx="50" cy="50" r="8" fill="#6366f1"/>
          <!-- 连接线和节点 -->
          <g stroke="#6366f1" stroke-width="2" fill="#6366f1">
            <!-- 上方节点 -->
            <line x1="50" y1="50" x2="50" y2="25"/>
            <circle cx="50" cy="25" r="4"/>
            <!-- 右上节点 -->
            <line x1="50" y1="50" x2="68" y2="32"/>
            <circle cx="68" cy="32" r="4"/>
            <!-- 右方节点 -->
            <line x1="50" y1="50" x2="75" y2="50"/>
            <circle cx="75" cy="50" r="4"/>
            <!-- 右下节点 -->
            <line x1="50" y1="50" x2="68" y2="68"/>
            <circle cx="68" cy="68" r="4"/>
            <!-- 下方节点 -->
            <line x1="50" y1="50" x2="50" y2="75"/>
            <circle cx="50" cy="75" r="4"/>
            <!-- 左下节点 -->
            <line x1="50" y1="50" x2="32" y2="68"/>
            <circle cx="32" cy="68" r="4"/>
            <!-- 左方节点 -->
            <line x1="50" y1="50" x2="25" y2="50"/>
            <circle cx="25" cy="50" r="4"/>
            <!-- 左上节点 -->
            <line x1="50" y1="50" x2="32" y2="32"/>
            <circle cx="32" cy="32" r="4"/>
          </g>
          <!-- 动画效果的小点 -->
          <circle cx="50" cy="25" r="2" fill="#6366f1" opacity="0.8">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/>
          </circle>
          <circle cx="75" cy="50" r="2" fill="#6366f1" opacity="0.8">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite" begin="0.5s"/>
          </circle>
          <circle cx="50" cy="75" r="2" fill="#6366f1" opacity="0.8">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite" begin="1s"/>
          </circle>
          <circle cx="25" cy="50" r="2" fill="#6366f1" opacity="0.8">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite" begin="1.5s"/>
          </circle>
        </svg>
      </div>
      <h1 class="chat-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="title-icon">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>
        </svg>
        <span>Chat-KG</span>
      </h1>
    </header>

    <!-- 消息列表（使用 props 传入的 messages） -->
    <main class="message-list">
      <div v-if="messages.length === 0" class="welcome-message">
        <p>👋 你好！有什么可以帮助你的吗？</p>
      </div>
      <div 
        v-for="(message, index) in messages" 
        :key="index" 
        :class="['message', message.sender]"
      >
        <div :class="['avatar', message.sender]">
          <i v-if="message.sender === 'ai'" class="fas fa-robot"></i>
          <i v-if="message.sender === 'user'" class="fas fa-user"></i>
        </div>
        <div class="message-content">
          <!-- 替换原来的pre标签为div，并使用v-html渲染解析后的HTML -->
          <div class="markdown-content" v-html="parseMarkdown(message.text)"></div>
          <span class="timestamp">{{ message.timestamp }}</span>
        </div>
      </div>

      <!-- 加载状态指示器 -->
      <div v-if="isLoading" class="typing-indicator">
        <div class="avatar ai">
          <i class="fas fa-robot"></i>
        </div>
        <div class="typing-dots">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    </main>

    <!-- 输入区域 -->
    <footer class="chat-input">
      <form @submit.prevent="sendMessage" class="input-form">
        <div class="input-wrapper">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="input-icon">
            <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" fill="currentColor"/>
          </svg>
          <textarea
            v-model="userInput"
            placeholder="输入你的消息..."
            class="message-input"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.enter.shift="handleShiftEnter"
            :disabled="isLoading"
          ></textarea>
        </div>
        <button 
          type="submit" 
          class="send-button"
          :disabled="!userInput.trim() || isLoading"
          :class="{ 'loading': isLoading, 'active': userInput.trim() }"
        >
          <div v-if="isLoading" class="loading-spinner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="31.416" stroke-dashoffset="31.416">
                <animate attributeName="stroke-dasharray" dur="2s" values="0 31.416;15.708 15.708;0 31.416" repeatCount="indefinite"/>
                <animate attributeName="stroke-dashoffset" dur="2s" values="0;-15.708;-31.416" repeatCount="indefinite"/>
              </circle>
            </svg>
          </div>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" fill="currentColor"/>
          </svg>
        </button>
      </form>
    </footer>
  </div>
</template>

<script setup>
import { ref, watch, defineEmits, defineProps} from 'vue';
import axios from 'axios';
import { marked } from 'marked';
import DOMPurify from 'dompurify';  // 导入dompurify

// 添加Markdown解析方法
const parseMarkdown = (text) => {
  // 先将Markdown转换为HTML，再净化HTML防止XSS攻击
  return DOMPurify.sanitize(marked.parse(text));
};

// 接收父组件传入的当前对话消息列表
const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  }
});
const emit = defineEmits(['messageAdded', 'clearChat', 'graphAdded']);
const userInput = ref('');
const messages = ref([...props.messages]);
const isLoading = ref(false);

// 发送消息函数
const sendMessage = () => {
  const messageText = userInput.value.trim();
  
  if (!messageText) return;
  
  // 用户消息添加到列表
  const userMessage = {
    sender: 'user',
    text: messageText,
    timestamp: getCurrentTime()
  };
  emit('messageAdded', userMessage);
  userInput.value = '';

  // 请求AI接口
  isLoading.value = true; // 新增：加载状态显示
  const userString = { message: userMessage.text }; // 无需reactive，普通对象即可

  axios.post("http://localhost:5000/reply", userString)
    .then(response => {
      const aiMessage = {
        sender: 'ai',
        text: response.data.message,
        timestamp: getCurrentTime()
      };
      console.log(response.data.graphData);
      console.log(response.data.message);
      // 触发消息添加事件
      emit('messageAdded', aiMessage);
      //发送 graph 数据
      
      const graphData = response.data.graphData;
      emit('graphAdded', graphData);
    })
    .catch(error => {
      console.error("请求出错：", error);
      const errorMessage = {
        sender: 'system',
        text: '请求AI回复失败，请稍后再试',
        timestamp: getCurrentTime()
      };
      // 触发消息添加事件
      emit('messageAdded', errorMessage);
    })
    .finally(() => {
      isLoading.value = false; // 新增：无论成功失败，关闭加载状态
    });
};

// 处理Shift+Enter换行（原有逻辑不变）
const handleShiftEnter = () => {
  userInput.value += "\n";
};

// 获取当前时间（格式化，原有逻辑不变）
const getCurrentTime = () => {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

// 监听消息变化，自动滚动到底部（原有逻辑不变）
watch(messages, () => {
  scrollToBottom();
});

watch(
  () => props.messages,
  (newMessages) => {
    messages.value = [...newMessages];
  },
  { deep: true } // 监听数组内部变化
);
// 滚动到最新消息（原有逻辑不变）
const scrollToBottom = () => {
  setTimeout(() => {
    const chatContainer = document.querySelector('.chat-messages');
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }, 0);
};
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(226, 232, 240, 0.8);
}

.chat-header {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: 16px 20px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.2);
}

.chat-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  display: flex;
  align-items: center;
}

.title-icon {
  margin-right: 8px;
  color: #6366f1;
  flex-shrink: 0;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.welcome-message {
  text-align: center;
  color: #64748b;
  font-size: 14px;
  padding: 40px 20px;
  background: rgba(248, 250, 252, 0.8);
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.6);
  margin: 20px 0;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
  animation: messageSlideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.ai {
  align-self: flex-start;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.avatar::before {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  border-radius: 50%;
  background: linear-gradient(45deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  z-index: -1;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.avatar:hover::before {
  opacity: 1;
}

.avatar.user {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
  color: white;
  box-shadow: 0 4px 16px rgba(6, 182, 212, 0.3);
}

.avatar.user:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(6, 182, 212, 0.4);
}

.avatar.ai {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.3);
}

.avatar.ai:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
}

.message-content {
  background: #ffffff;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.6);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  position: relative;
  font-size: 14px;
  line-height: 1.5;
  color: #334155;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.message.user .message-content {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.message.ai .message-content {
  background: rgba(248, 250, 252, 0.8);
  border: 1px solid rgba(226, 232, 240, 0.6);
}

.timestamp {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  text-align: right;
  font-weight: 400;
}

.message.ai .timestamp {
  text-align: left;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: rgba(248, 250, 252, 0.8);
  border-top: 1px solid rgba(226, 232, 240, 0.6);
}

.typing-dots {
  display: flex;
  gap: 4px;
}

.typing-dot {
  width: 6px;
  height: 6px;
  background: #6366f1;
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out;
}

.typing-dot:nth-child(1) { animation-delay: -0.32s; }
.typing-dot:nth-child(2) { animation-delay: -0.16s; }

.chat-input {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-top: 1px solid rgba(226, 232, 240, 0.6);
  padding: 16px 20px;
}

.input-form {
  display: flex;
  gap: 4px;
  align-items: center;
}

.input-wrapper {
  position: relative;
  flex: 1;
}

.input-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
  font-size: 14px;
  z-index: 1;
  transition: color 0.2s ease;
}

.input-wrapper:focus-within .input-icon {
  color: #6366f1;
}

.message-input {
  width: 100%;
  min-height: 44px;
  max-height: 120px;
  padding: 12px 16px 12px 36px;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  background: #ffffff;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.message-input:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.message-input::placeholder {
  color: #94a3b8;
}

.send-button {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.2);
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
  margin-left: 0px;
}

.send-button.active {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  box-shadow: 0 3px 10px rgba(99, 102, 241, 0.3);
  transform: scale(1.02);
}

.send-button.loading {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  cursor: wait;
}

.loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-spinner svg {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.send-button svg {
  width: 18px;
  height: 18px;
  transform: translateX(1px);
}

.send-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.send-button:active {
  transform: translateY(0);
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.2);
}

.send-button:disabled {
  background: #e2e8f0;
  color: #94a3b8;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.input-hint {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 8px;
  text-align: center;
}

/* Markdown 样式 */
.message-content h1,
.message-content h2,
.message-content h3,
.message-content h4,
.message-content h5,
.message-content h6 {
  margin: 12px 0 8px 0;
  font-weight: 600;
  color: inherit;
}

.message-content p {
  margin: 8px 0;
  line-height: 1.6;
}

.message-content ul,
.message-content ol {
  margin: 8px 0;
  padding-left: 20px;
}

.message-content li {
  margin: 4px 0;
  line-height: 1.5;
}

.message-content code {
  background: rgba(0, 0, 0, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
}

.message.user .message-content code {
  background: rgba(255, 255, 255, 0.2);
}

.message-content pre {
  background: rgba(0, 0, 0, 0.05);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
  border: 1px solid rgba(226, 232, 240, 0.6);
}

.message.user .message-content pre {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.message-content pre code {
  background: none;
  padding: 0;
  font-size: 13px;
}

/* 动画效果 */
@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes typingBounce {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .chat-container {
    border-radius: 12px;
  }
  
  .chat-header {
    padding: 12px 16px;
  }
  
  .message-list {
    padding: 16px;
    gap: 12px;
  }
  
  .message {
    max-width: 90%;
    gap: 8px;
  }
  
  .avatar {
    width: 32px;
    height: 32px;
    font-size: 12px;
  }
  
  .message-content {
    padding: 10px 12px;
    font-size: 13px;
  }
  
  .chat-input {
    padding: 12px 16px;
  }
  
  .input-form {
    gap: 8px;
  }
  
  .message-input {
    padding: 8px 12px;
    font-size: 13px;
  }
  
  .send-button {
    width: 36px;
    height: 36px;
  }
}
</style>