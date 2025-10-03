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

// 计算过滤后的数据
const filteredData = computed(() => {
  return filterGraphData(graphData, maxNodes.value, maxLinks.value);
});

// 数据过滤函数 - 优化版本，保持图谱连通性
const filterGraphData = (data, nodeLimit, linkLimit) => {
  // 计算每个节点的连接数
  const nodeConnections = {};
  data.links.forEach(link => {
    nodeConnections[link.source] = (nodeConnections[link.source] || 0) + 1;
    nodeConnections[link.target] = (nodeConnections[link.target] || 0) + 1;
  });
  
  // 使用广度优先搜索选择连通的节点子集
  const selectConnectedNodes = (nodes, links, limit) => {
    if (nodes.length <= limit) return nodes;
    
    // 找到连接数最多的节点作为起始点
    const startNode = nodes.reduce((max, node) => 
      (nodeConnections[node.id] || 0) > (nodeConnections[max.id] || 0) ? node : max
    );
    
    const selected = new Set([startNode.id]);
    const queue = [startNode.id];
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    
    // 构建邻接表
    const adjacency = {};
    links.forEach(link => {
      if (!adjacency[link.source]) adjacency[link.source] = [];
      if (!adjacency[link.target]) adjacency[link.target] = [];
      adjacency[link.source].push(link.target);
      adjacency[link.target].push(link.source);
    });
    
    // 广度优先搜索，优先选择连接数多的邻居
    while (queue.length > 0 && selected.size < limit) {
      const current = queue.shift();
      const neighbors = adjacency[current] || [];
      
      // 按连接数排序邻居节点
      const sortedNeighbors = neighbors
        .filter(id => !selected.has(id) && nodeMap.has(id))
        .sort((a, b) => (nodeConnections[b] || 0) - (nodeConnections[a] || 0));
      
      for (const neighborId of sortedNeighbors) {
        if (selected.size >= limit) break;
        selected.add(neighborId);
        queue.push(neighborId);
      }
    }
    
    return Array.from(selected).map(id => nodeMap.get(id));
  };
  
  // 选择连通的节点子集
  const selectedNodes = selectConnectedNodes(data.nodes, data.links, nodeLimit);
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
  background: #f5f5f5;
}

.control-panel {
  position: absolute;
  top: 20px;
  left: 20px;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  z-index: 1000;
  min-width: 300px;
}

.control-group {
  margin-bottom: 15px;
}

.control-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #333;
}

.slider {
  width: 150px;
  margin-right: 10px;
}

.number-input {
  width: 60px;
  padding: 2px 5px;
  border: 1px solid #ddd;
  border-radius: 3px;
  margin-right: 10px;
}

.count-display {
  font-size: 12px;
  color: #666;
}

.reset-btn, .show-all-btn {
  padding: 8px 15px;
  margin-right: 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.reset-btn {
  background: #007bff;
  color: white;
}

.reset-btn:hover {
  background: #0056b3;
}

.show-all-btn {
  background: #28a745;
  color: white;
}

.show-all-btn:hover {
  background: #1e7e34;
}

.stats {
  border-top: 1px solid #eee;
  padding-top: 15px;
  margin-top: 15px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
}

.stat-label {
  color: #666;
  font-weight: 500;
}

.stat-value {
  color: #333;
  font-weight: bold;
}

.d3-graph {
  width: 100%;
  height: 100%;
}

.error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: red;
  font-size: 18px;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
</style>

