async function conectarAPI() {
    try {
        const res = await fetch('http://127.0.0.1:8000/api/metricas');
        const data = await res.json();
        document.getElementById('velas').innerText = data.total_velas;
        document.getElementById('runs').innerText = data.total_runs;
        document.getElementById('cuarentena').innerText = data.total_cuarentena;
        console.log("✅ Datos reales conectados:", data);
    } catch (error) {
        console.error("❌ Error de conexión:", error);
        document.getElementById('velas').innerText = "Error de conexión";
    }
}
document.addEventListener('DOMContentLoaded', conectarAPI);
