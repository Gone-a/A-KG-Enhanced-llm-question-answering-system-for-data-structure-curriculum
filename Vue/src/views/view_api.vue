<template>
  <div class="api-setting-page">
    <div class="api-setting-card">
      <h2 class="api-setting-title">API 设置</h2>
      <div class="setting-group">
        <div class="form-item">
          <label class="form-label">模型</label>
          <input
            type="text"
            v-model="apiSettings.model"
            placeholder="请输入模型名称"
            class="api-input"
          />
        </div>
        <div class="form-item">
          <label class="form-label">API Key</label>
          <input
            type="text"
            v-model="apiSettings.apiKey"
            placeholder="请输入API Key"
            class="api-input"
          />
        </div>
        <div class="form-item">
          <label class="form-label">Base URL</label>
          <input
            type="text"
            v-model="apiSettings.baseUrl"
            placeholder="请输入Base URL"
            class="api-input"
          />
        </div>
        <button
          @click="saveApiSettings"
          :disabled="!isApiSettingsValid"
          class="submit-btn"
        >
          保存API设置
        </button>
      </div>

      <h2 class="api-setting-title" style="margin-top: 30px;">数据库设置</h2>
      <div class="setting-group">
        <div class="form-item">
          <label class="form-label">Bolt URL</label>
          <input
            type="text"
            v-model="dbSettings.boltUrl"
            placeholder="请输入Bolt URL"
            class="api-input"
          />
        </div>
        <div class="form-item">
          <label class="form-label">用户名</label>
          <input
            type="text"
            v-model="dbSettings.username"
            placeholder="请输入用户名"
            class="api-input"
          />
        </div>
        <div class="form-item">
          <label class="form-label">密码</label>
          <input
            type="password"
            v-model="dbSettings.password"
            placeholder="请输入密码"
            class="api-input"
          />
        </div>
        <div class="form-item">
          <label class="form-label">Neo4j浏览器</label>
          <input
            type="text"
            v-model="dbSettings.browserUrl"
            placeholder="请输入Neo4j浏览器地址"
            class="api-input"
          />
        </div>
        <button
          @click="saveDbSettings"
          :disabled="!isDbSettingsValid"
          class="submit-btn"
        >
          保存数据库设置
        </button>
      </div>

      <p v-if="feedbackMsg" class="feedback-msg">{{ feedbackMsg }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import axios from 'axios';

// 从localStorage读取保存的设置，没有则使用默认值
const loadFromLocalStorage = () => {
  const savedApi = localStorage.getItem('apiSettings');
  const savedDb = localStorage.getItem('dbSettings');
  
  return {
    api: savedApi ? JSON.parse(savedApi) : { model: '', apiKey: '', baseUrl: '' },
    db: savedDb ? JSON.parse(savedDb) : { boltUrl: '', username: '', password: '', browserUrl: '' }
  };
};

// 初始化设置数据
const { api: initialApi, db: initialDb } = loadFromLocalStorage();

// API设置数据
const apiSettings = ref(initialApi);

// 数据库设置数据
const dbSettings = ref(initialDb);

const feedbackMsg = ref('');

// 监听设置变化，自动保存到localStorage
watch(apiSettings, (newValue) => {
  localStorage.setItem('apiSettings', JSON.stringify(newValue));
}, { deep: true });

watch(dbSettings, (newValue) => {
  localStorage.setItem('dbSettings', JSON.stringify(newValue));
}, { deep: true });

// 验证API设置是否有效
const isApiSettingsValid = computed(() => {
  return apiSettings.value.model.trim() && 
         apiSettings.value.apiKey.trim() && 
         apiSettings.value.baseUrl.trim();
});

// 验证数据库设置是否有效
const isDbSettingsValid = computed(() => {
  return dbSettings.value.boltUrl.trim() && 
         dbSettings.value.username.trim() && 
         dbSettings.value.browserUrl.trim();
});

// 保存API设置
const saveApiSettings = async () => {
  feedbackMsg.value = '正在保存API设置...';
  console.log(apiSettings);

  try {
    const response = await axios.post('http://localhost:5000/set_api', {
      apiSettings: apiSettings.value
    });
    feedbackMsg.value = response.data || 'API设置保存成功';
  } catch (error) {
    feedbackMsg.value = 'API设置保存失败，请检查地址或网络';
    console.error('保存API设置失败：', error);
  }
};

// 保存数据库设置
const saveDbSettings = async () => {
  feedbackMsg.value = '正在保存数据库设置...';
  console.log(dbSettings);
  
  try {
    const response = await axios.post('http://localhost:5000/set_database', {
      dbSettings: dbSettings.value
    });
    feedbackMsg.value = response.data || '数据库设置保存成功';
  } catch (error) {
    feedbackMsg.value = '数据库设置保存失败，请检查地址或网络';
    console.error('保存数据库设置失败：', error);
  }
};
</script>

<style scoped>
.api-setting-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #ffffff 0%, #ffffff 100%);
  padding: 20px;
  position: relative;
  overflow: hidden;
}

.api-setting-page::before {
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

.api-setting-card {
  width: 600px;
  max-width: 90vw;
  padding: 40px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 24px;
  box-shadow: 
    0 25px 50px rgba(0, 0, 0, 0.15),
    0 10px 20px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.2);
  position: relative;
  animation: slideInUp 0.6s ease-out;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.api-setting-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 24px;
  color: #2d3748;
  padding-bottom: 16px;
  border-bottom: 3px solid transparent;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  position: relative;
}

.api-setting-title::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  width: 60px;
  height: 3px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 2px;
}

.setting-group {
  margin-bottom: 32px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.setting-group:hover {
  background: rgba(255, 255, 255, 0.7);
  transform: translateY(-2px);
  box-shadow: 
    0 8px 25px rgba(0, 0, 0, 0.1),
    0 4px 8px rgba(0, 0, 0, 0.05);
}

.form-item {
  margin-bottom: 20px;
  position: relative;
}

.form-label {
  display: block;
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #4a5568;
  letter-spacing: 0.5px;
  position: relative;
}

.form-label::before {
  content: '●';
  color: #667eea;
  margin-right: 8px;
  font-size: 12px;
}

.api-input {
  width: 100%;
  padding: 16px 20px;
  margin-bottom: 8px;
  border: 2px solid rgba(102, 126, 234, 0.2);
  border-radius: 12px;
  box-sizing: border-box;
  font-size: 15px;
  font-weight: 500;
  color: #2d3748;
  background: rgba(255, 255, 255, 0.8);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

.api-input:focus {
  outline: none;
  border-color: #667eea;
  background: rgba(255, 255, 255, 1);
  box-shadow: 
    0 0 0 4px rgba(102, 126, 234, 0.1),
    0 4px 12px rgba(102, 126, 234, 0.15);
  transform: translateY(-1px);
}

.api-input::placeholder {
  color: #a0aec0;
  font-weight: 400;
}

.submit-btn {
  width: 100%;
  padding: 16px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 
    0 6px 20px rgba(102, 126, 234, 0.4),
    0 3px 6px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow: hidden;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.submit-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.submit-btn::after {
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

.submit-btn:hover {
  transform: translateY(-3px);
  box-shadow: 
    0 10px 30px rgba(102, 126, 234, 0.5),
    0 6px 12px rgba(0, 0, 0, 0.15);
}

.submit-btn:hover::before {
  left: 100%;
}

.submit-btn:active {
  transform: translateY(-1px) scale(0.98);
}

.submit-btn:active::after {
  width: 200px;
  height: 200px;
}

.submit-btn:disabled {
  background: linear-gradient(135deg, #94a3b8 0%, #64748b 100%);
  cursor: not-allowed;
  transform: none;
  box-shadow: 
    0 2px 8px rgba(148, 163, 184, 0.3),
    0 1px 3px rgba(0, 0, 0, 0.1);
}

.submit-btn:disabled::before,
.submit-btn:disabled::after {
  display: none;
}

.submit-btn:disabled:hover {
  transform: none;
  box-shadow: none;
}

.feedback-msg {
  margin-top: 20px;
  font-size: 15px;
  font-weight: 600;
  text-align: center;
  padding: 16px 20px;
  border-radius: 12px;
  background: rgba(102, 126, 234, 0.1);
  color: #4a5568;
  border: 1px solid rgba(102, 126, 234, 0.2);
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 成功状态样式 */
.feedback-msg.success {
  background: rgba(72, 187, 120, 0.1);
  color: #2f855a;
  border-color: rgba(72, 187, 120, 0.2);
}

/* 错误状态样式 */
.feedback-msg.error {
  background: rgba(239, 68, 68, 0.1);
  color: #c53030;
  border-color: rgba(239, 68, 68, 0.2);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .api-setting-card {
    width: 100%;
    padding: 24px;
    margin: 10px;
  }
  
  .api-setting-title {
    font-size: 20px;
    margin-bottom: 20px;
  }
  
  .setting-group {
    padding: 16px;
    margin-bottom: 24px;
  }
  
  .api-input {
    padding: 12px 16px;
    font-size: 14px;
  }
  
  .submit-btn {
    padding: 14px 20px;
    font-size: 14px;
  }
}

/* 添加一些微妙的动画效果 */
.form-item {
  animation: fadeInUp 0.4s ease-out;
}

.form-item:nth-child(1) { animation-delay: 0.1s; }
.form-item:nth-child(2) { animation-delay: 0.2s; }
.form-item:nth-child(3) { animation-delay: 0.3s; }
.form-item:nth-child(4) { animation-delay: 0.4s; }

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

/* 输入框聚焦时的标签动画 */
.form-item:focus-within .form-label {
  color: #667eea;
  transform: translateY(-2px);
  transition: all 0.3s;
}

.form-item:focus-within .form-label::before {
  color: #764ba2;
  transform: scale(1.2);
  transition: all 0.3s;
}
</style>