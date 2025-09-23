<template>
  <div class="graph-container">
    <div ref="graphContainer" class="d3-graph"></div>
    <div v-if="error" class="error">错误: {{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as d3 from 'd3';
import graphData from '@/data/graph.json'; // 引入你的JSON数据

const graphContainer = ref(null);
const error = ref('');
let simulation = null;

// 绘制图形 - 确保此函数被正确调用
const drawGraph = () => {
  // 深拷贝数据，避免修改原始响应式数据
  const dataCopy = JSON.parse(JSON.stringify(graphData)); 
  
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

onMounted(() => {
  setTimeout(drawGraph, 0); // 确保DOM渲染完成后初始化
});

onUnmounted(() => {
  if (simulation) simulation.stop(); // 组件卸载时停止模拟
});
</script>

