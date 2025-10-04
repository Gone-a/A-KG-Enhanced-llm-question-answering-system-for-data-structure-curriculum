<template>
  <div class="graph-container">
    <!-- 数据控制面板 -->
    <div class="control-panel">
      <div class="control-group">
        <label>节点数量限制:</label>
        <input 
          type="range" 
          v-model="maxNodes" 
          :min="10" 
          :max="totalNodes" 
          :step="10"
          class="slider"
        />
        <input 
          type="number" 
          v-model="maxNodes" 
          :min="10" 
          :max="totalNodes"
          class="number-input"
        />
        <span class="count-display">{{ maxNodes }} / {{ totalNodes }}</span>
      </div>
      
      <div class="control-group">
        <label>边数量限制:</label>
        <input 
          type="range" 
          v-model="maxLinks" 
          :min="10" 
          :max="totalLinks" 
          :step="10"
          class="slider"
        />
        <input 
          type="number" 
          v-model="maxLinks" 
          :min="10" 
          :max="totalLinks"
          class="number-input"
        />
        <span class="count-display">{{ maxLinks }} / {{ totalLinks }}</span>
      </div>
      
      <div class="control-group">
        <button @click="resetToDefault" class="reset-btn">重置为默认</button>
        <button @click="showAll" class="show-all-btn">显示全部</button>
      </div>
      
      <div class="stats">
        <div class="stat-item">
          <span class="stat-label">当前显示:</span>
          <span class="stat-value">{{ filteredData.nodes.length }} 节点, {{ filteredData.links.length }} 边</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">总数据量:</span>
          <span class="stat-value">{{ totalNodes }} 节点, {{ totalLinks }} 边</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">显示比例:</span>
          <span class="stat-value">
            节点 {{ Math.round((filteredData.nodes.length / totalNodes) * 100) }}%, 
            边 {{ Math.round((filteredData.links.length / totalLinks) * 100) }}%
          </span>
        </div>
      </div>
    </div>
    
    <div ref="graphContainer" class="d3-graph"></div>
    <div v-if="error" class="error">错误: {{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue';
import * as d3 from 'd3';
import graphData from '@/data/graph.json'; // 引入你的JSON数据

const graphContainer = ref(null);
const error = ref('');
let simulation = null;

// 数据控制相关的响应式变量
const totalNodes = ref(graphData.nodes.length);
const totalLinks = ref(graphData.links.length);
const maxNodes = ref(Math.min(50, totalNodes.value)); // 默认显示50个节点
const maxLinks = ref(Math.min(100, totalLinks.value)); // 默认显示100条边

// 添加随机种子，确保每次滑块变化时都产生不同的节点组合
const randomSeed = ref(Date.now());

// 计算过滤后的数据
const filteredData = computed(() => {
  return filterGraphData(graphData, maxNodes.value, maxLinks.value, randomSeed.value);
});

// 监听滑块变化，更新随机种子
watch([maxNodes, maxLinks], () => {
  randomSeed.value = Date.now() + Math.random() * 1000;
});

// 数据过滤函数 - 随机选择版本，每次都显示不同的节点
const filterGraphData = (data, nodeLimit, linkLimit, seed = Date.now()) => {
  // 计算每个节点的连接数
  const nodeConnections = {};
  data.links.forEach(link => {
    nodeConnections[link.source] = (nodeConnections[link.source] || 0) + 1;
    nodeConnections[link.target] = (nodeConnections[link.target] || 0) + 1;
  });
  
  // 随机选择节点，同时保持一定的连通性
  const selectRandomConnectedNodes = (nodes, links, limit) => {
    if (nodes.length <= limit) return nodes;
    
    // 创建节点映射和邻接表
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const adjacency = {};
    links.forEach(link => {
      if (!adjacency[link.source]) adjacency[link.source] = [];
      if (!adjacency[link.target]) adjacency[link.target] = [];
      adjacency[link.source].push(link.target);
      adjacency[link.target].push(link.source);
    });
    
    // 使用传入的种子作为随机种子，确保每次调用都不同
    const randomSeed = seed + Math.random();
    const seededRandom = () => {
      const x = Math.sin(randomSeed * Math.random()) * 10000;
      return x - Math.floor(x);
    };
    
    // 随机打乱节点数组
    const shuffledNodes = [...nodes].sort(() => seededRandom() - 0.5);
    
    // 分层选择策略：70%随机选择，30%基于连通性选择
    const randomCount = Math.floor(limit * 0.7);
    // const connectedCount = limit - randomCount; // 保留注释，说明设计思路
    
    const selected = new Set();
    
    // 第一阶段：完全随机选择70%的节点
    for (let i = 0; i < Math.min(randomCount, shuffledNodes.length); i++) {
      selected.add(shuffledNodes[i].id);
    }
    
    // 第二阶段：基于连通性选择剩余30%的节点，确保图的连通性
    if (selected.size < limit) {
      const remaining = shuffledNodes.filter(node => !selected.has(node.id));
      const queue = [];
      
      // 从已选择的节点中随机选择一个作为起点
      const selectedArray = Array.from(selected);
      const startNodeId = selectedArray[Math.floor(seededRandom() * selectedArray.length)];
      queue.push(startNodeId);
      
      while (queue.length > 0 && selected.size < limit) {
        const current = queue.shift();
        const neighbors = adjacency[current] || [];
        
        // 随机打乱邻居节点
        const shuffledNeighbors = neighbors
          .filter(id => !selected.has(id) && nodeMap.has(id))
          .sort(() => seededRandom() - 0.5);
        
        for (const neighborId of shuffledNeighbors) {
          if (selected.size >= limit) break;
          selected.add(neighborId);
          queue.push(neighborId);
          
          // 随机决定是否继续添加这个节点的邻居到队列
          if (seededRandom() > 0.5) {
            break;
          }
        }
      }
      
      // 如果还没达到限制，随机添加剩余节点
      while (selected.size < limit && remaining.length > 0) {
        const randomIndex = Math.floor(seededRandom() * remaining.length);
        const randomNode = remaining.splice(randomIndex, 1)[0];
        if (randomNode) {
          selected.add(randomNode.id);
        }
      }
    }
    
    return Array.from(selected).map(id => nodeMap.get(id));
  };
  
  // 选择连通的节点子集
  const selectedNodes = selectRandomConnectedNodes(data.nodes, data.links, nodeLimit);
  const selectedNodeIds = new Set(selectedNodes.map(node => node.id));
  
  // 只保留连接选中节点的边
  const validLinks = data.links.filter(link => 
    selectedNodeIds.has(link.source) && selectedNodeIds.has(link.target)
  );
  
  // 限制边的数量，优先保留连接重要节点的边
  const limitedLinks = validLinks
    .sort((a, b) => {
      const aScore = (nodeConnections[a.source] || 0) + (nodeConnections[a.target] || 0);
      const bScore = (nodeConnections[b.source] || 0) + (nodeConnections[b.target] || 0);
      return bScore - aScore;
    })
    .slice(0, linkLimit);
  
  return {
    nodes: selectedNodes.map(node => ({ id: node.id, name: node.name })),
    links: limitedLinks
  };
};

// 控制面板操作函数
const resetToDefault = () => {
  maxNodes.value = Math.min(50, totalNodes.value);
  maxLinks.value = Math.min(100, totalLinks.value);
};

const showAll = () => {
  maxNodes.value = totalNodes.value;
  maxLinks.value = totalLinks.value;
};

// 清除图形
const clearGraph = () => {
  if (graphContainer.value) {
    d3.select(graphContainer.value).selectAll("*").remove();
  }
  if (simulation) {
    simulation.stop();
    simulation = null;
  }
};

// 绘制图形 - 使用过滤后的数据
const drawGraph = () => {
  // 使用过滤后的数据
  const dataCopy = JSON.parse(JSON.stringify(filteredData.value)); 
  
  // 清除现有图形
  clearGraph();
  
  // 验证容器是否存在
  if (!graphContainer.value) {
    console.error("图形容器元素未找到");
    return;
  }

  const container = graphContainer.value;
  const width = container.clientWidth || 1200;
  const height = container.clientHeight || 800;

  console.log("宽长");
  console.log(width);
  console.log(height);
  
  // 创建SVG元素
  const svg = d3.select(container)
    .append("svg")
    .attr("width", "100%")    // SVG宽度占满容器
    .attr("height", "100%")   // SVG高度占满容器
    .attr("viewBox", `0 0 ${width} ${height}`) // 定义可视区域（与容器宽高同步）
    .attr("preserveAspectRatio", "xMidYMid meet"); // 让图形在viewBox中居中
    
  // 创建箭头标记
  svg.append("defs").selectAll("marker")
    .data(["end"])
    .enter().append("marker")
    .attr("id", d => d)
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 25)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#999");
  
  // 创建力导向图模拟
  simulation = d3.forceSimulation(dataCopy.nodes)
    .force("link", d3.forceLink(dataCopy.links).id(d => d.id).distance(100)) // 边更短 → 拉力使节点更近
    .force("charge", d3.forceManyBody().strength(-150))
    .force("center", d3.forceCenter(width / 2, height / 2)) // 保持中心引力
    .force("x", d3.forceX(width / 2).strength(0.05)) // 新增：向中心X轴聚集（温和拉力）
    .force("y", d3.forceY(height / 2).strength(0.05)) // 新增：向中心Y轴聚集（温和拉力）
    .force("collision", d3.forceCollide().radius(50)); // 碰撞半径减小 → 节点可更靠近

  // 绘制连接线
  const link = svg.append("g")
    .attr("class", "links")
    .selectAll("line")
    .data(dataCopy.links)
    .enter().append("line")
    .attr("stroke", "#999")
    .attr("stroke-opacity", 0.6)
    .attr("stroke-width", 1.5)
    .attr("marker-end", "url(#end)");

  const linkLabels = svg.append("g")
  .attr("class", "link-labels")
  .selectAll("text")
  .data(dataCopy.links)
  .enter().append("text")
  .text(d => d.relation)
  .attr("font-size", 12)
  .attr("fill", "#333")
  .attr("text-anchor", "middle")
  .attr("pointer-events", "none");
  
  // 创建节点组
  const node = svg.append("g")
    .attr("class", "nodes")
    .selectAll(".node")
    .data(dataCopy.nodes)
    .enter().append("g")
    .attr("class", "node")
    .call(d3.drag()
      .on("start", dragStarted)
      .on("drag", dragged)
      .on("end", dragEnded));
  
  // 添加节点圆圈
  node.append("circle")
    .attr("r", 25)
    .attr("fill", d => {
      // 字符串转哈希值的工具函数
      function stringToHash(str) {
        let hash = 0;
        if (str.length === 0) return hash;
        for (let i = 0; i < str.length; i++) {
          const char = str.charCodeAt(i);
          hash = ((hash << 5) - hash) + char; // 位运算生成哈希
          hash = hash & hash; // 转换为32位整数（确保为非负数基础）
        }
        return hash;
      }
      // 用哈希值生成色相（0-359范围）
      const hash = stringToHash(d.id);
      const hue = Math.abs(hash) % 360;
      return `hsl(${hue}, 70%, 60%)`;
    })
    .attr("stroke", "#fff")
    .attr("stroke-width", 2);
  
  // 添加节点文本标签
  node.append("text")
    .attr("dy", ".35em")
    .attr("text-anchor", "middle")
    .text(d => d.name)
    .attr("font-size", "12px")
    .attr("fill", "#fff")
    .attr("pointer-events", "none");
  
  // 更新力导向图布局
  simulation.on("tick", () => {
    // 限制节点在视图范围内
    dataCopy.nodes.forEach(d => {
      d.x = Math.max(30, Math.min(width - 30, d.x));
      d.y = Math.max(30, Math.min(height - 30, d.y));
    });
    
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);
    
    linkLabels.each(function(d) {
      const midX = (d.source.x + d.target.x) / 2; // 边的中点X
      const midY = (d.source.y + d.target.y) / 2; // 边的中点Y
      d3.select(this)
        .attr("x", midX)
        .attr("y", midY);
    });
    node.attr("transform", d => `translate(${d.x},${d.y})`);
  });
  
  // 拖拽事件处理函数
  function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }
  
  function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }
  
  function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }
};

// 监听窗口大小变化，触发布局重算
watch(
  () => [window.innerWidth, window.innerHeight],
  () => {
    if (simulation) simulation.alpha(0.1).restart();
  },
  { immediate: false, deep: true }
);

// 监听过滤数据变化，重新绘制图形
watch(filteredData, () => {
  drawGraph();
}, { deep: true });

// 组件挂载后绘制图形
onMounted(() => {
  drawGraph();
});

onUnmounted(() => {
  if (simulation) simulation.stop(); // 组件卸载时停止模拟
});
</script>

<style scoped>
.graph-container {
  width: 100%;
  height: 100vh;
  position: relative;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  overflow: hidden;
}

.graph-container::before {
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

.control-panel {
  position: absolute;
  top: 30px;
  right: 30px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  padding: 24px;
  border-radius: 20px;
  box-shadow: 
    0 20px 40px rgba(0, 0, 0, 0.1),
    0 8px 16px rgba(0, 0, 0, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
  z-index: 1000;
  min-width: 320px;
  max-width: 380px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.control-panel:hover {
  transform: translateY(-2px);
  box-shadow: 
    0 25px 50px rgba(0, 0, 0, 0.15),
    0 10px 20px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.control-group {
  margin-bottom: 20px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: all 0.3s;
}

.control-group:hover {
  background: rgba(255, 255, 255, 0.7);
  transform: translateY(-1px);
}

.control-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 700;
  color: #2d3748;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.slider {
  width: 140px;
  margin-right: 12px;
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(to right, #e2e8f0, #cbd5e0);
  outline: none;
  transition: all 0.3s;
}

.slider::-webkit-slider-thumb {
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  cursor: pointer;
  box-shadow: 
    0 4px 12px rgba(102, 126, 234, 0.4),
    0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
}

.slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
  box-shadow: 
    0 6px 16px rgba(102, 126, 234, 0.5),
    0 3px 6px rgba(0, 0, 0, 0.15);
}

.number-input {
  width: 60px;
  padding: 8px 12px;
  border: 2px solid rgba(102, 126, 234, 0.2);
  border-radius: 8px;
  margin-right: 12px;
  font-size: 13px;
  font-weight: 600;
  color: #2d3748;
  background: rgba(255, 255, 255, 0.8);
  transition: all 0.3s;
}

.number-input:focus {
  outline: none;
  border-color: #667eea;
  background: rgba(255, 255, 255, 1);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.count-display {
  font-size: 12px;
  color: #718096;
  font-weight: 600;
  background: rgba(102, 126, 234, 0.1);
  padding: 4px 8px;
  border-radius: 6px;
}

.reset-btn, .show-all-btn {
  padding: 12px 20px;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  margin-right: 12px;
  margin-bottom: 8px;
  box-shadow: 
    0 4px 15px rgba(245, 87, 108, 0.4),
    0 2px 4px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow: hidden;
}

.reset-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.reset-btn::after {
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

.reset-btn:hover {
  transform: translateY(-2px);
  box-shadow: 
    0 8px 25px rgba(245, 87, 108, 0.5),
    0 4px 8px rgba(0, 0, 0, 0.15);
}

.reset-btn:hover::before {
  left: 100%;
}

.reset-btn:active {
  transform: translateY(-1px) scale(0.98);
}

.reset-btn:active::after {
  width: 100px;
  height: 100px;
}

.show-all-btn {
  padding: 12px 20px;
  background: linear-gradient(135deg, #48cc6c 0%, #2dd4bf 100%);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  margin-right: 12px;
  margin-bottom: 8px;
  box-shadow: 
    0 4px 15px rgba(72, 204, 108, 0.4),
    0 2px 4px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow: hidden;
}

.show-all-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.show-all-btn::after {
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

.show-all-btn:hover {
  transform: translateY(-2px);
  box-shadow: 
    0 8px 25px rgba(72, 187, 120, 0.5),
    0 4px 8px rgba(0, 0, 0, 0.15);
}

.show-all-btn:hover::before {
  left: 100%;
}

.show-all-btn:active {
  transform: translateY(-1px) scale(0.98);
}

.show-all-btn:active::after {
  width: 100px;
  height: 100px;
}

.stats {
  border-top: 2px solid rgba(102, 126, 234, 0.1);
  padding-top: 20px;
  margin-top: 20px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
  border-radius: 12px;
  padding: 20px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(102, 126, 234, 0.1);
}

.stat-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.stat-label {
  color: #4a5568;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.stat-label::before {
  content: '●';
  color: #667eea;
  margin-right: 8px;
  font-size: 16px;
}

.stat-value {
  color: #2d3748;
  font-weight: 700;
  background: rgba(102, 126, 234, 0.1);
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
}

.d3-graph {
  width: 100%;
  height: 100%;
  border-radius: 20px;
  overflow: hidden;
}

.error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #e53e3e;
  font-size: 18px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  padding: 30px 40px;
  border-radius: 20px;
  box-shadow: 
    0 20px 40px rgba(229, 62, 62, 0.2),
    0 8px 16px rgba(0, 0, 0, 0.1);
  border: 2px solid rgba(229, 62, 62, 0.2);
  text-align: center;
  max-width: 400px;
}

.error::before {
  content: '⚠️';
  display: block;
  font-size: 32px;
  margin-bottom: 16px;
}

/* 添加一些微妙的动画效果 */
@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.control-panel {
  animation: slideInRight 0.5s ease-out;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}

.stat-label::before {
  animation: pulse 2s infinite;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .control-panel {
    top: 20px;
    right: 20px;
    left: 20px;
    min-width: auto;
    max-width: none;
    padding: 20px;
  }
  
  .control-group {
    margin-bottom: 16px;
    padding: 12px;
  }
  
  .slider {
    width: 100px;
  }
  
  .reset-btn, .show-all-btn {
    padding: 10px 16px;
    font-size: 12px;
    margin-right: 8px;
    margin-bottom: 8px;
  }
}
</style>

