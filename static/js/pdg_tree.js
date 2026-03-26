function togglePDGTree() {
    const win = document.getElementById("pdg-tree-window");
    if (!win) return;
    const isOpen = win.style.display === "flex";
    if (isOpen) {
        win.style.display = "none";
    } else {
        win.style.display = "flex";
        // ↓ "guest_user" を削除。user_idはサーバー側で認証済みのものを使う
        loadPDGTree();
    }
}

// ↓ userId引数を廃止。Authorization headerでサーバーに認証させる
async function loadPDGTree() {
    const container = document.getElementById("pdg-tree-content");
    if (!container) return;

    container.innerHTML = "<p style='color:#aaa;font-size:13px;padding:12px'>読み込み中...</p>";

    // ↓ URLからuser_idを除去。tokenをheaderで渡す
    const accessToken = sessionStorage.getItem("haruhi_access_token") || "";
    const res = await fetch(`/get_pdg_tree`, {
        headers: {
            "Authorization": `Bearer ${accessToken}`
        }
    });
    const nodes = await res.json();

    if (!nodes || nodes.length === 0) {
        container.innerHTML = "<p style='color:#aaa;font-size:13px;padding:12px'>まだ問いの系譜がありません</p>";
        return;
    }

    renderPDGTree(nodes, container);
}

function renderPDGTree(nodes, container) {
    const idMap = {};
    nodes.forEach(n => { idMap[n.id] = { ...n, children: [] }; });
    nodes.forEach(n => {
        if (n.parent && idMap[n.parent]) {
            idMap[n.parent].children.push(idMap[n.id]);
        }
    });

    const roots = nodes
        .filter(n => !n.parent || !idMap[n.parent])
        .map(n => idMap[n.id]);

    const virtualRoot = { id: "__root__", text: "root", children: roots };

    const d3Root = d3.hierarchy(virtualRoot);
    const nodeSize = [180, 100];
    const treeLayout = d3.tree().nodeSize(nodeSize);
    treeLayout(d3Root);

    // 全ノードの座標範囲を計算
    const allNodes = d3Root.descendants().filter(d => d.data.id !== "__root__");
    const xs = allNodes.map(d => d.x);
    const ys = allNodes.map(d => d.y);
    const minX = Math.min(...xs) - 100;
    const maxX = Math.max(...xs) + 100;
    const minY = Math.min(...ys) - 40;
    const maxY = Math.max(...ys) + 60;
    const svgW = maxX - minX;
    const svgH = maxY - minY;

    container.innerHTML = "";

    const svg = d3.select(container)
        .append("svg")
        .attr("width", svgW)
        .attr("height", svgH)
        .attr("viewBox", `${minX} ${minY} ${svgW} ${svgH}`);

    // エッジ
    svg.selectAll(".link")
        .data(d3Root.links().filter(d => d.source.data.id !== "__root__"))
        .join("line")
        .attr("stroke", "#ccc")
        .attr("stroke-width", 1.5)
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

// ノード
    const node = svg.selectAll(".node")
        .data(allNodes)
        .join("g")
        .attr("transform", d => `translate(${d.x}, ${d.y})`)
        .style("cursor", "pointer");

    // 同テキストの件数を事前カウント
    const textCount = {};
    allNodes.forEach(d => {
        const t = d.data.text || "";
        textCount[t] = (textCount[t] || 0) + 1;
    });

    node.append("circle")
        .attr("r", 10)
        .attr("fill", d => d.parent?.data.id === "__root__" ? "#7c3aed" : "#3b82f6")
        .attr("stroke", "#fff")
        .attr("stroke-width", 2.5);

    // 重複バッジ（同テキストが2件以上のノードに数字を表示）
    node.filter(d => textCount[d.data.text || ""] > 1)
        .append("circle")
        .attr("cx", 8).attr("cy", -8)
        .attr("r", 7)
        .attr("fill", "#ef4444")
        .attr("stroke", "#fff")
        .attr("stroke-width", 1.5);

    node.filter(d => textCount[d.data.text || ""] > 1)
        .append("text")
        .attr("x", 8).attr("y", -8)
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "central")
        .attr("font-size", "9px")
        .attr("fill", "#fff")
        .attr("font-weight", "bold")
        .text(d => textCount[d.data.text || ""]);

    // ラベル
    node.append("text")
        .attr("dy", -20)
        .attr("text-anchor", "middle")
        .attr("font-size", "11px")
        .attr("fill", "#444")
        .text(d => {
            const t = d.data.text || "";
            return t.length > 16 ? t.substring(0, 16) + "…" : t;
        });

    // ツールチップ
    const tooltip = d3.select(document.getElementById("pdg-tree-window"))
        .append("div")
        .style("position", "absolute")
        .style("background", "#1e1b4b")
        .style("color", "#fff")
        .style("padding", "8px 12px")
        .style("border-radius", "8px")
        .style("font-size", "12px")
        .style("max-width", "240px")
        .style("line-height", "1.6")
        .style("pointer-events", "none")
        .style("opacity", 0)
        .style("z-index", "9999")
        .style("transition", "opacity 0.15s");

    node.on("mouseover", function(event, d) {
            const t = d.data.text || "";
            const count = textCount[t];
            const depth = d.depth - 1;
            let html = `<strong>${t}</strong>`;
            if (count > 1) {
                html += `<br><span style="color:#fca5a5">⚠ 同じ問いが系譜内に ${count} 件あります</span>`;
            }
            html += `<br><span style="color:#a5b4fc">深さ: ${depth} 階層</span>`;
            if (d.children && d.children.length > 0) {
                html += `<br><span style="color:#6ee7b7">派生: ${d.children.length} 問い</span>`;
            }
            tooltip.html(html).style("opacity", 1);
        })
        .on("mousemove", function(event) {
            const winRect = document.getElementById("pdg-tree-window").getBoundingClientRect();
            tooltip
                .style("left", (event.clientX - winRect.left + 12) + "px")
                .style("top",  (event.clientY - winRect.top  - 10) + "px");
        })
        .on("mouseout", function() {
            tooltip.style("opacity", 0);
        })
        .on("click", function(event, d) {
            alert("【問い】\n\n" + d.data.text);
        });
}