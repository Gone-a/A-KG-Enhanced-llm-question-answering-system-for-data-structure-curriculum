import { defineStore } from 'pinia'
import axios from 'axios'

// 初始化默认的图形数据（对应你view_home.vue中的myGraphData）
const defaultGraphData = {
  nodes: [

  ],
  links: [
    
  ]
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    chatHistories: JSON.parse(localStorage.getItem('chatHistories')) || [
        { id: Date.now(), title: '新对话', messages: [], graph: { nodes: [], links: [] } }
    ],
    currentChatIndex: 0
  }),
  getters: {
    // 获取当前对话（对应你view_home.vue中的currentChat）
    currentChat(state) {
      return state.chatHistories[state.currentChatIndex];
    }
  },
  actions: {
    // 保存数据到localStorage（持久化）
    saveToLocal() {
      localStorage.setItem('chatHistories', JSON.stringify(this.chatHistories))
    },

    // 新建对话（对应你view_home.vue中的createNewChat）
    createNewChat() {
        console.log("1")
        console.log(this.chatHistories)
        const newChat = {
          id: Date.now(),
          title: '新对话',
          messages: [],
          graph: defaultGraphData
        }
        this.chatHistories.push(newChat)
        this.currentChatIndex = this.chatHistories.length - 1
        this.saveToLocal() // 保存到本地
    },

    // 切换对话（对应你view_home.vue中的switchChat）
    switchChat(index) {
        if (index < 0 || index >= this.chatHistories.length) {
            console.warn('无效索引，自动切换到第一个对话');
            this.currentChatIndex = 0;
            return;
        }
        this.currentChatIndex = index;
     
        if (this.currentChat) {
            axios.post("http://localhost:5000/switchChat",this.currentChat.messages)
            .then(response => {
            console.log(this.currentChat.messages);
            console.log(response.data);
            })
            .catch(error => {
            console.log(this.currentChat.messages);
            console.error("请求出错：", error);
            });
        }
    },

    // 添加消息到当前对话（对应你view_home.vue中的handleMessageAdded）
    handleMessageAdded(newMessage) {
      
        this.currentChat.messages.push(newMessage);
        // 首次消息设置标题
        if (this.currentChat.messages.length === 1) {
          this.currentChat.title = newMessage.text.slice(0, 10) || '新对话'
        }
        this.saveToLocal() // 保存到本地
    },

    // 清空当前对话消息（对应你view_home.vue中的clearCurrentChat）
    clearCurrentChat() {
      this.currentChat.messages = []
      this.saveToLocal()
    },

    // 更新当前对话的图形数据（对应你view_home.vue中的graphshow）
    graphshow(graphdata) {
      console.log("2");
      console.log(graphdata);
      if (graphdata?.nodes && graphdata?.links) {
        this.currentChat.graph = { ...graphdata } // 触发响应式更新
        this.saveToLocal()
      }
    },

    // 删除对话（对应你view_home.vue中的deleteChat）
    deleteChat(index) {
      if (this.chatHistories.length <= 1) {
          // 保留至少一个对话，避免数组为空
          this.chatHistories[0] = { id: Date.now(), title: '新对话', messages: [], graph: {} };
          this.currentChatIndex = 0;
          return;
      }
      this.chatHistories.splice(index, 1);
      // 调整当前索引，避免越界
      if (this.currentChatIndex === index) {
          this.currentChatIndex = Math.max(0, index - 1); // 切换到前一个对话
      } else if (this.currentChatIndex > index) {
          this.currentChatIndex--; // 索引前移一位
      }
    }
  }
})