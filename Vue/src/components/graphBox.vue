<template>
  <div class="graph-container">
    <div ref="graphContainer" class="graph-view"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, onUnmounted, defineProps } from 'vue';
import * as d3 from 'd3';

// 接收父组件传入的图形数据
const props = defineProps({
  graphData: {
    type: Object,
    default: () => ({ nodes: [], links: [] }),
    description: '包含nodes和links的JSON数据'
  }
});

// 组件内部状态
const graphContainer = ref(null);
const graphStatus = ref("初始化中...");
let simulation = null;

// 清除当前图形
const clearGraph = () => {
  if (graphContainer.value) {
    d3.select(graphContainer.value).selectAll("*").remove();
  }
  if (simulation) {
    simulation.stop();
    simulation = null;
  }
};

// 绘制图形 - 确保此函数被正确调用
const drawGraph = (data) => {
  // 深拷贝数据，避免修改原始响应式数据
  const dataCopy = JSON.parse(JSON.stringify(data)); 
  // 清空现有图形
  clearGraph();
  
  // 验证容器是否存在
  if (!graphContainer.value) {
    graphStatus.value = "错误: 图形容器不存在";
    console.error("图形容器元素未找到");
    return;
  }
  
  // 验证数据格式
  if (!data || !data.nodes || !data.links) {
    graphStatus.value = "错误: 无效的数据格式";
    console.error("无效的数据格式，必须包含nodes和links属性");
    return;
  }
  
  // 验证数据内容
  if (data.nodes.length === 0) {
    graphStatus.value = "警告: 没有节点数据";
    return;
  }
  
  graphStatus.value = "正在绘制图形...";
  
  // 获取容器尺寸并确保有明确的大小
  const container = graphContainer.value;
  const width = container.clientWidth || 800;
  const height = container.clientHeight || 600;

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
    .force("link", d3.forceLink(dataCopy.links).id(d => d.id).distance(150))
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(width / 2, height / 2)) // 中心力指向容器中心
    .force("collision", d3.forceCollide().radius(60));
  
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
    .attr("fill", d => `hsl(${d.id * 40 % 360}, 70%, 60%)`)
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
  
  // 模拟完成后更新状态
  simulation.on("end", () => {
    graphStatus.value = `图形绘制完成 (节点: ${dataCopy.nodes.length}, 边: ${dataCopy.links.length})`;
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
  
  console.log("图形绘制函数已执行", data);
  graphStatus.value = "图形绘制中...";
};

// 当组件挂载时初始化 - 确保在此处调用drawGraph
onMounted(() => {
  graphStatus.value = "组件已挂载，准备绘制图形";
  // 监听窗口大小变化
  window.addEventListener('resize', handleResize);
  
  // 确保DOM更新后再绘制图形
  nextTick(() => {
    console.log("首次绘制图形");
    const currentData = props.graphData;
    drawGraph(currentData);
  });
});

// 当组件卸载时清理
onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  clearGraph();
});

// 处理窗口大小变化
const handleResize = () => {
  graphStatus.value = "窗口大小变化，重绘图形";
  const currentData = props.graphData;
  drawGraph(currentData);
};

// 监听数据变化，更新图形 - 确保数据变化时调用drawGraph
watch([() => props.graphData], () => {
  nextTick(() => {
    console.log("数据变化，重绘图形");
    const currentData = props.graphData;
    drawGraph(currentData);
  });
},{ flush: 'post' });
</script>

<style scoped>
.graph-container {
  width: 100%;
  height: 100%;
  min-height: 600px; /* 确保有足够的高度 */
  position: relative;
  padding: 20px;
  box-sizing: border-box;
}

.controls {
  position: absolute;
  top: 15px;
  right: 15px;
  z-index: 10;
  display: flex;
  gap: 15px;
  align-items: center;
}

.btn {
  background-color: #42b983;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.3s;
}

.btn:hover {
  background-color: #359e75;
}

.status-info {
  font-size: 14px;
  color: #666;
  background-color: rgba(255, 255, 255, 0.8);
  padding: 4px 8px;
  border-radius: 4px;
}

/* 关键修改：确保图形容器有明确的尺寸 */
.graph-view {
  width: 100%;
  height: 100%;
  min-height: 500px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  overflow: hidden;
  background-color: #f9f9f9;
}

.nodes circle {
  transition: all 0.3s ease;
}

.nodes circle:hover {
  stroke: #333;
  stroke-width: 3;
}

.links line {
  transition: all 0.3s ease;
}

.nodes text {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-weight: 500;
}
</style>
