<template>
  <div class="nav-container">
    <!-- 导航栏主体 -->
    <nav class="navbar">
      <!-- 导航标题（可选，增加品牌感） -->
      <div class="nav-title">
        <span class="title-text">KG</span>
      </div>

      <!-- 导航链接区域 -->
      <div class="nav-links">
        <!-- 首页导航（活跃状态有蓝色下划线） -->
        <router-link
          to="/"
          class="nav-link"
          :class="{ 'active': $route.path === '/' }"
          exact
        >
          <i class="icon-home"></i>
          <span class="link-text">首页</span>
        </router-link>

        <!-- 图页面导航 -->
        <router-link
          to="/graph"
          class="nav-link"
          :class="{ 'active': $route.path === '/graph' }"
          exact
        >
          <i class="icon-graph"></i>
          <span class="link-text">图</span>
        </router-link>

        <router-link
          to="/api"
          class="nav-link"
          :class="{ 'active': $route.path === '/api' }"
          exact
        >
          <i class="icon-api"></i>
          <span class="link-text">设置</span>
        </router-link>
      </div>
    </nav>

    <!-- 路由内容显示区域（增加过渡动画） -->
    <transition name="page-fade">
      <router-view class="content-container"></router-view>
    </transition>
  </div>
</template>

<style scoped>
/* 全局容器样式 */
.nav-container {
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  position: relative;
}

.nav-container::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    radial-gradient(circle at 20% 80%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 40% 40%, rgba(6, 182, 212, 0.06) 0%, transparent 50%);
  pointer-events: none;
  z-index: -1;
}

/* 导航栏样式：现代化玻璃态设计 */
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2.5rem;
  height: 70px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(226, 232, 240, 0.6);
  border-top: none;
  border-left: none;
  border-right: none;
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 
    0 4px 20px rgba(0, 0, 0, 0.08),
    0 1px 3px rgba(0, 0, 0, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.4);
  color: #1e293b;
  position: sticky;
  top: 0;
  z-index: 100;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.navbar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(99, 102, 241, 0.2) 20%, 
    rgba(99, 102, 241, 0.4) 50%, 
    rgba(99, 102, 241, 0.2) 80%, 
    transparent 100%);
}

.navbar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  height: 1px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(99, 102, 241, 0.15) 50%, 
    transparent 100%);
}

/* 导航标题样式 - 更加精致 */
.nav-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.4rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  position: relative;
}

.title-text {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 2px 4px rgba(99, 102, 241, 0.1);
  position: relative;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.title-text::after {
  content: '';
  position: absolute;
  bottom: -4px;
  left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-radius: 1px;
  opacity: 0.6;
}

/* 导航链接容器 */
.nav-links {
  display: flex;
  gap: 0.5rem;
  background: rgba(255, 255, 255, 0.6);
  padding: 6px 8px;
  border-radius: 50px;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(226, 232, 240, 0.4);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

/* 导航链接基础样式 - 现代化胶囊设计 */
.nav-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 10px 16px;
  color: #64748b;
  font-size: 0.9rem;
  font-weight: 500;
  text-decoration: none;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  border-radius: 25px;
  background: transparent;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.nav-link::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(139, 92, 246, 0.08) 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

/* 导航链接hover效果 */
.nav-link:hover {
  color: #6366f1;
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 
    0 2px 8px rgba(99, 102, 241, 0.12),
    0 1px 3px rgba(0, 0, 0, 0.05);
}

.nav-link:hover::before {
  opacity: 1;
}

/* 活跃链接样式 */
.nav-link.active {
  color: white;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  box-shadow: 
    0 2px 8px rgba(99, 102, 241, 0.3),
    0 1px 3px rgba(0, 0, 0, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.nav-link.active::before {
  opacity: 0;
}

.nav-link.active::after {
  display: none;
}

/* 图标样式优化 */
.icon-home::before,
.icon-graph::before,
.icon-api::before {
  font-size: 1.1rem;
  transition: transform 0.3s ease;
}

.nav-link:hover .icon-home::before,
.nav-link:hover .icon-graph::before,
.nav-link:hover .icon-api::before {
  transform: scale(1.05);
}

/* 内容区域样式 */
.content-container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem 1rem;
  position: relative;
}

/* 页面切换过渡动画优化 */
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(15px) scale(0.98);
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 响应式适配优化 */
@media (max-width: 768px) {
  .navbar {
    flex-direction: column;
    height: auto;
    padding: 1.2rem 1rem;
    backdrop-filter: blur(15px);
  }

  .nav-links {
    margin-top: 1rem;
    gap: 0.3rem;
    flex-wrap: wrap;
    justify-content: center;
    padding: 4px 6px;
  }

  .nav-link {
    padding: 8px 12px;
    font-size: 0.85rem;
  }

  .content-container {
    padding: 1rem;
  }
  
  .nav-title {
    font-size: 1.3rem;
  }
}
</style>