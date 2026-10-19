const $ = (id) => document.getElementById(id);
let LIMITE_DESPACHO = 250;
let ASSINATURA = "";
// tamanho típico do nome do documento na árvore, ex.: "Ofício 585 (151163165)"
const NOME_OFICIO_ESTIMADO = "Ofício 0000 (000000000)";
const PLACEHOLDER_DOC = "[Documento a ser criado]";
const CAMPOS_SALVOS = ["referencia", "destinatario", "signatario", "atribuir", "etiqueta", "tipoDocumento"];
const ETAPAS = ["login", "processo", "leitura", "ia", "oficio", "despacho", "atribuicao"];

let militares = [];
let resultadoAtual = null;
let analiseAtual = null;
let opcaoSelecionada = null;
let autoridadeAtual = null;
let destinatarioEditado = false;

const escapar = (t) => t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const tipoDocumento = () => $("tipoDocumento").value || "Ofício";

// ---------- carga inicial ----------
async function iniciar() {
  try {
    await fetch("/health").then((r) => { if (!r.ok) throw r; });
    $("apiStatus").className = "api-status on";
    $("apiStatus").lastChild.textContent = "API online";
  } catch {
    $("apiStatus").className = "api-status off";
    $("apiStatus").lastChild.textContent = "API offline";
  }

  const [config, lista, etiquetas] = await Promise.all([
    fetch("/configuracao").then((r) => r.json()),
    fetch("/militares").then((r) => r.json()),
    fetch("/etiquetas").then((r) => r.json()),
  ]);
  militares = lista;
  ASSINATURA = config.despacho_assinatura;
  LIMITE_DESPACHO = config.despacho_max_caracteres;
  $("iaStatus").textContent = config.ia_configurada ? `IA: ${config.ia_modelo}` : "IA simulada (sem OPENAI_API_KEY)";
  $("iaStatus").classList.toggle("off", !config.ia_configurada);

  const opcoes = militares.map((m) => `<option value="${m.cpf}">${escapar(m.nome_guerra)} — ${escapar(m.nome)}</option>`).join("");
  $("signatario").innerHTML = `<option value="" disabled selected>Selecione…</option>${opcoes}`;
  $("atribuir").innerHTML = `<option value="" disabled selected>Selecione…</option>${opcoes}`;
  $("etiqueta").innerHTML = etiquetas.map((e) => `<option>${escapar(e)}</option>`).join("");
  $("etiqueta").value = "Aguardando Despacho do Major";

  for (const id of CAMPOS_SALVOS) {
    const salvo = localStorage.getItem(`oficio.${id}`);
    if (salvo) $(id).value = salvo;
  }
  mostrarSignatario();
  atualizarRotulosTipo();
  atualizarDespacho();
}

const militar = (cpf) => militares.find((m) => m.cpf === cpf);

function mostrarSignatario() {
  const m = militar($("signatario").value);
  $("signerCard").innerHTML = m
    ? `<strong>${escapar(m.nome.toUpperCase())}, ${escapar(m.graduacao.toUpperCase())}</strong><small>${escapar(m.funcao)}</small>`
    : `<small>O nome, a graduação e a função entram no rodapé do ofício (quando o tipo for Ofício).</small>`;
}

function atualizarRotulosTipo() {
  const tipo = tipoDocumento();
  $("labelCriarDoc").textContent = `Criar o ${tipo}`;
  $("liCriarDoc").textContent = `Criar ${tipo}`;
}

// ---------- gerador de despacho (anotação do marcador; regras de app/modelos.py) ----------
// documento citado = sempre o criado no fluxo: ["o {oficio}"]
let documentosDespacho = ["o {oficio}"];
// enquanto o usuário não digitar na mensagem, ela acompanha o formulário
let mensagemEditada = false;

function formatarItens(lista) {
  if (lista.length <= 1) return lista.join("");
  return lista.slice(0, -1).join(", ") + " e " + lista.at(-1);
}

function montarDespacho() {
  const m = militar($("atribuir").value);
  let assunto = $("assunto").value.trim().replace(/\.$/, "");
  if (!m || !assunto || !documentosDespacho.length) return "";
  if (/^[A-ZÀ-Ý][a-zà-ÿ]/.test(assunto)) assunto = assunto[0].toLowerCase() + assunto.slice(1);
  const complemento = $("despachoComplemento").value.trim().replace(/\.$/, "");
  const inicio = `${m.tratamento} ${m.nome_guerra}`.trim();
  const verbo = documentosDespacho.length === 1 ? "trata" : "tratam";
  // encaminhamento do dadosmil já traz "Encaminho a V.Sa. para análise e despacho"
  const docs = formatarItens(documentosDespacho).replaceAll("{oficio}", PLACEHOLDER_DOC);
  let texto = `${inicio}. ${m.encaminhamento} ${docs}, que ${verbo} de ${assunto}. `;
  if (complemento) texto += `${complemento}. `;
  return texto + `${m.despedida} ${ASSINATURA}.`;
}

const textoDespacho = () => $("despachoTexto").value.trim();
const textoDespachoApi = () => textoDespacho().replaceAll(PLACEHOLDER_DOC, "{oficio}");
const tamanhoDespacho = () =>
  textoDespachoApi().replaceAll("{oficio}", NOME_OFICIO_ESTIMADO).length;

function atualizarContador() {
  const tamanho = tamanhoDespacho();
  const contador = $("contador");
  contador.textContent = `~${tamanho}/${LIMITE_DESPACHO}`;
  contador.className = "counter" + (tamanho > LIMITE_DESPACHO ? " err" : tamanho > LIMITE_DESPACHO - 30 ? " warn" : "");
}

function atualizarDespacho() {
  if (!mensagemEditada) $("despachoTexto").value = montarDespacho();
  atualizarContador();
}

function alertaDespacho(tipo, html) {
  $("alertaDespacho").className = `alerta ${tipo}`;
  $("alertaDespacho").innerHTML = html;
}

function gerarTexto() {
  if (!$("atribuir").value || !$("assunto").value.trim()) {
    return alertaDespacho("warning", "⚠️ Preencha os campos: Atribuir para e Assunto");
  }
  if (!$("criarOficio").checked) {
    return alertaDespacho("warning", "⚠️ Ative \"Criar o documento\" para citar o documento criado no fluxo");
  }
  mensagemEditada = false;
  atualizarDespacho();
  const tamanho = tamanhoDespacho();
  if (tamanho > LIMITE_DESPACHO) {
    return alertaDespacho("error", `❌ <strong>Texto com ~${tamanho} caracteres</strong> (limite ${LIMITE_DESPACHO}). Reduza o complemento ou o assunto.`);
  }
  alertaDespacho("success", `✅ <strong>Texto válido!</strong> ~${tamanho}/${LIMITE_DESPACHO} caracteres`);
  setTimeout(() => $("geradorDespacho").classList.add("hidden"), 2000);
}

$("btnGerarDespacho").addEventListener("click", () => {
  $("geradorDespacho").classList.toggle("hidden");
  $("alertaDespacho").className = "alerta hidden";
});
$("btnGerarTexto").addEventListener("click", gerarTexto);
$("despachoTexto").addEventListener("input", () => {
  mensagemEditada = textoDespacho() !== "";
  atualizarContador();
});
["assunto", "despachoComplemento"].forEach((id) => $(id).addEventListener("input", atualizarDespacho));
$("atribuir").addEventListener("change", atualizarDespacho);
$("criarOficio").addEventListener("change", (e) => {
  // sem criar documento nesta execução, não há "{oficio}" para citar
  documentosDespacho = e.target.checked ? ["o {oficio}"] : [];
  atualizarDespacho();
});
$("tipoDocumento").addEventListener("change", () => {
  atualizarRotulosTipo();
  atualizarDespacho();
});
$("signatario").addEventListener("change", async () => {
  mostrarSignatario();
  localStorage.setItem("oficio.signatario", $("signatario").value);
  await recalcularDestinatario();
});
["destinatario", "analiseDestinatario"].forEach((id) => {
  if ($(id)) $(id).addEventListener("input", () => { destinatarioEditado = true; });
});
CAMPOS_SALVOS.forEach((id) => $(id).addEventListener("change", () => localStorage.setItem(`oficio.${id}`, $(id).value)));

async function recalcularDestinatario() {
  if (destinatarioEditado || !autoridadeAtual?.nome) return;
  const params = new URLSearchParams({
    autoridade: autoridadeAtual.nome,
    signatario_cpf: $("signatario").value || "",
  });
  try {
    const r = await fetch(`/destinatario?${params}`).then((res) => res.json());
    aplicarDestinatarioSugerido(r.destinatario || "");
  } catch {
    /* mantém o valor atual */
  }
}

function aplicarDestinatarioSugerido(dest) {
  $("destinatario").value = dest;
  if ($("analiseDestinatario")) $("analiseDestinatario").value = dest;
  $("avisoDestinatario").classList.toggle("hidden", Boolean(dest));
  if ($("analiseAvisoDest")) $("analiseAvisoDest").classList.toggle("hidden", Boolean(dest));
}

// ---------- execução ----------
function sincronizarCamposAnalise() {
  if (!$("analiseAssunto")) return;
  const assunto = $("analiseAssunto").value.trim();
  const dest = $("analiseDestinatario").value.trim();
  if (assunto) $("assunto").value = assunto;
  if (dest) $("destinatario").value = dest;
  atualizarDespacho();
}

function payload(simular) {
  const body = {
    processo: $("processo").value.trim(),
    referencia: $("referencia").value.trim(),
    assunto: $("assunto").value.trim(),
    destinatario: $("destinatario").value.trim(),
    complementar: $("complementar").value.trim(),
    signatario_cpf: $("signatario").value,
    tipo_documento: tipoDocumento(),
    atribuir_cpf: $("atribuir").value,
    etiqueta: $("etiqueta").value,
    despacho_complemento: $("despachoComplemento").value.trim(),
    despacho_documentos: documentosDespacho,
    despacho_texto: textoDespachoApi(),
    simular,
    criar_oficio: $("criarOficio").checked,
    adicionar_marcador: $("adicionarMarcador").checked,
    atribuir: $("atribuirProc").checked,
  };
  // etapa 2: só envia se houver opção escolhida (sem isso o backend segue o fluxo direto de hoje)
  if (analiseAtual && opcaoSelecionada) {
    body.id_analise = analiseAtual.id_analise;
    body.opcao_escolhida = opcaoSelecionada;
    body.informacoes_adicionais = ($("analiseInfoExtra")?.value || "").trim();
  }
  return body;
}

function validar() {
  if (!$("form").reportValidity()) return false;
  if ($("assunto").value.trim().length < 3) {
    alert("Informe o Assunto (mín. 3 caracteres) ou use Analisar demanda.");
    $("assunto").focus();
    return false;
  }
  if ($("destinatario").value.trim().length < 3) {
    alert("Informe o Destinatário (mín. 3 caracteres) ou use Analisar demanda.");
    $("destinatario").focus();
    return false;
  }
  const tamanho = tamanhoDespacho();
  if ($("adicionarMarcador").checked && !textoDespacho()) {
    alert("Gere ou digite a mensagem do despacho (✨ Gerar Despacho).");
    return false;
  }
  if ($("adicionarMarcador").checked && tamanho > LIMITE_DESPACHO) {
    alert(`O despacho tem ~${tamanho} caracteres (limite ${LIMITE_DESPACHO}). Encurte o assunto ou o complemento.`);
    return false;
  }
  return true;
}

function validarAnalise() {
  if (!$("processo").value.trim()) {
    alert("Informe o número do processo.");
    $("processo").focus();
    return false;
  }
  if (!$("referencia").value.trim()) {
    alert("Informe o Documento respondido (referência) para a análise.");
    $("referencia").focus();
    return false;
  }
  return true;
}

function prepararPainel(simular) {
  $("log").innerHTML = "";
  $("barra").style.width = "0";
  $("resultado").classList.add("hidden");
  $("badge").className = "badge run";
  $("badge").textContent = simular ? "pré-visualizando" : "executando";
  const pulados = new Set();
  if (simular || !$("criarOficio").checked) pulados.add("oficio");
  if (simular || !$("adicionarMarcador").checked) pulados.add("despacho");
  if (simular || !$("atribuirProc").checked) pulados.add("atribuicao");
  document.querySelectorAll("#timeline li").forEach((li) => {
    li.className = pulados.has(li.dataset.etapa) ? "pulado" : "";
  });
}

function marcarEtapa(etapa, tipo) {
  const indice = ETAPAS.indexOf(etapa);
  document.querySelectorAll("#timeline li").forEach((li) => {
    if (li.classList.contains("pulado")) return;
    const i = ETAPAS.indexOf(li.dataset.etapa);
    if (i < indice || (i === indice && tipo === "success")) li.className = "feito";
    else if (i === indice) li.className = "ativo";
  });
  if (etapa === "fim") document.querySelectorAll("#timeline li:not(.pulado)").forEach((li) => (li.className = "feito"));
}

function registrar(evento) {
  const p = document.createElement("p");
  p.className = evento.tipo;
  p.textContent = evento.mensagem;
  $("log").appendChild(p);
  $("log").scrollTop = $("log").scrollHeight;
  if (evento.progresso != null) $("barra").style.width = `${evento.progresso}%`;
  if (evento.etapa) marcarEtapa(evento.etapa, evento.tipo);
  if (evento.tipo === "error") {
    $("badge").className = "badge err";
    $("badge").textContent = "erro";
    const ativo = document.querySelector("#timeline li.ativo");
    if (ativo) ativo.className = "erro";
  }
}

function mostrarResultado(dados) {
  resultadoAtual = dados;
  const tipo = dados.tipo_documento || tipoDocumento();
  $("badge").className = "badge ok";
  $("badge").textContent = dados.simulacao ? "pré-visualizado" : "concluído";
  $("resTitulo").textContent = dados.simulacao ? "Pré-visualização (nada foi gravado)" : `Resultado — ${dados.oficio}`;
  $("resDocTitulo").textContent = tipo;
  $("resOficio").innerHTML = dados.oficio_html || "";
  $("resDespacho").textContent = dados.despacho || "—";
  $("resAtribuido").textContent = dados.atribuido_a || (dados.simulacao ? "— (simulação)" : "— (etapa desativada)");
  $("resQtd").textContent = (dados.documentos || []).length;
  $("resDocs").innerHTML = (dados.documentos || []).map((d) => `<li>${escapar(d)}</li>`).join("");
  $("resultado").classList.remove("hidden");
  $("resultado").scrollIntoView({ behavior: "smooth" });
}

async function lerNdjson(resposta, aoResultado) {
  const leitor = resposta.body.getReader();
  const decodificador = new TextDecoder();
  let sobra = "";
  for (;;) {
    const { done, value } = await leitor.read();
    if (done) break;
    sobra += decodificador.decode(value, { stream: true });
    const linhas = sobra.split("\n");
    sobra = linhas.pop();
    for (const linha of linhas.filter((l) => l.trim())) {
      const evento = JSON.parse(linha);
      if (evento.tipo === "resultado") aoResultado(evento.dados);
      else registrar(evento);
    }
  }
}

async function executar(simular) {
  if (!validar()) return;
  const botoes = [$("btnExecutar"), $("btnSimular"), $("btnAnalisar")];
  botoes.forEach((b) => (b.disabled = true));
  prepararPainel(simular);
  try {
    const resposta = await fetch("/oficios/responder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload(simular)),
    });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      const detalhe = Array.isArray(erro.detail) ? erro.detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join("; ") : erro.detail;
      throw new Error(detalhe || `HTTP ${resposta.status}`);
    }
    await lerNdjson(resposta, mostrarResultado);
  } catch (e) {
    registrar({ tipo: "error", mensagem: `Falha: ${e.message}` });
  } finally {
    botoes.forEach((b) => (b.disabled = false));
  }
}

function mostrarAnalise(dados) {
  analiseAtual = dados;
  opcaoSelecionada = null;
  autoridadeAtual = dados.autoridade || null;
  destinatarioEditado = false;
  $("badge").className = "badge ok";
  $("badge").textContent = "análise pronta";
  $("analiseId").textContent = dados.id_analise ? `id ${dados.id_analise.slice(0, 8)}…` : "";
  $("analiseSignatario").textContent = dados.signatario_documento_respondido
    ? `Signatário do documento respondido: ${dados.signatario_documento_respondido}`
    : "Signatário do documento respondido: (não identificado)";

  $("analiseAssunto").value = dados.assunto || "";
  $("assunto").value = dados.assunto || "";

  // não sobrescreve signatário já escolhido (select ou localStorage)
  if (dados.signatario_cpf_sugerido && !$("signatario").value) {
    $("signatario").value = dados.signatario_cpf_sugerido;
    mostrarSignatario();
  }

  const dest = dados.destinatario_sugerido || "";
  aplicarDestinatarioSugerido(dest);
  // autoridade sem posto ainda: recalcula com o signatário atual do select
  if (!dest && autoridadeAtual) recalcularDestinatario();
  atualizarDespacho();

  $("analiseOpcoes").innerHTML = (dados.opcoes || []).map((o) => `
    <button type="button" class="opcao-card" data-id="${o.id}">
      <strong>${o.id}. ${escapar(o.titulo)}</strong>
      <span>${escapar(o.resumo)}</span>
    </button>`).join("");
  $("analiseInfoExtra").value = "";
  $("btnGerarDoc").disabled = true;
  $("analisePainel").classList.remove("hidden");
  $("analisePainel").scrollIntoView({ behavior: "smooth" });
}

$("analiseOpcoes").addEventListener("click", (e) => {
  const card = e.target.closest(".opcao-card");
  if (!card || !analiseAtual) return;
  const id = Number(card.dataset.id);
  opcaoSelecionada = (analiseAtual.opcoes || []).find((o) => o.id === id) || null;
  $("analiseOpcoes").querySelectorAll(".opcao-card").forEach((c) => {
    c.classList.toggle("selecionada", Number(c.dataset.id) === id);
  });
  $("btnGerarDoc").disabled = !opcaoSelecionada;
});

["analiseAssunto", "analiseDestinatario"].forEach((id) => {
  $(id).addEventListener("input", () => {
    if (id === "analiseAssunto") {
      $("assunto").value = $("analiseAssunto").value;
      atualizarDespacho();
    } else {
      destinatarioEditado = true;
      $("destinatario").value = $("analiseDestinatario").value;
      $("avisoDestinatario").classList.add("hidden");
      $("analiseAvisoDest").classList.add("hidden");
    }
  });
});

function confirmarGeracao(origemAnalise) {
  if (!validar()) return;
  const tipo = tipoDocumento();
  const etapas = [
    $("criarOficio").checked && `criar o ${tipo}`,
    $("adicionarMarcador").checked && `adicionar o marcador "${$("etiqueta").value}"`,
    $("atribuirProc").checked && `atribuir a ${militar($("atribuir").value)?.nome_guerra}`,
  ].filter(Boolean);
  const opcaoTxt = origemAnalise && opcaoSelecionada
    ? ` pela opção "${opcaoSelecionada.titulo}"`
    : "";
  $("confirmarTexto").textContent =
    `No processo ${$("processo").value.trim()}, a automação vai ${etapas.join(", ") || "apenas ler o processo"}${opcaoTxt}.`;
  $("confirmar").dataset.simular = "false";
  $("confirmar").showModal();
}

$("btnGerarDoc").addEventListener("click", () => {
  if (!analiseAtual || !opcaoSelecionada) return;
  sincronizarCamposAnalise();
  // grava no SEI (com confirmação); para simular=true use Pré-visualizar após escolher a opção
  confirmarGeracao(true);
});

async function analisar() {
  if (!validarAnalise()) return;
  const botoes = [$("btnExecutar"), $("btnSimular"), $("btnAnalisar")];
  botoes.forEach((b) => (b.disabled = true));
  $("analisePainel").classList.add("hidden");
  prepararPainel(true);
  $("badge").textContent = "analisando";
  // na análise só login/leitura/IA importam
  ["oficio", "despacho", "atribuicao"].forEach((e) => {
    const li = document.querySelector(`#timeline li[data-etapa="${e}"]`);
    if (li) li.className = "pulado";
  });
  try {
    const resposta = await fetch("/oficios/analisar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        processo: $("processo").value.trim(),
        referencia: $("referencia").value.trim(),
        complementar: $("complementar").value.trim(),
        signatario_cpf: $("signatario").value || "",
      }),
    });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      const detalhe = Array.isArray(erro.detail) ? erro.detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join("; ") : erro.detail;
      throw new Error(detalhe || `HTTP ${resposta.status}`);
    }
    await lerNdjson(resposta, mostrarAnalise);
  } catch (e) {
    registrar({ tipo: "error", mensagem: `Falha: ${e.message}` });
  } finally {
    botoes.forEach((b) => (b.disabled = false));
  }
}

$("form").addEventListener("submit", (e) => {
  e.preventDefault();
  sincronizarCamposAnalise();
  confirmarGeracao(Boolean(analiseAtual && opcaoSelecionada));
});
$("confirmarOk").addEventListener("click", () => {
  $("confirmar").close();
  executar($("confirmar").dataset.simular === "true");
});
$("cancelar").addEventListener("click", (e) => { e.preventDefault(); $("confirmar").close(); });
$("btnSimular").addEventListener("click", () => {
  sincronizarCamposAnalise();
  executar(true);
});
$("btnAnalisar").addEventListener("click", () => analisar());

$("btnLimpar").addEventListener("click", () => {
  ["processo", "assunto", "complementar", "despachoComplemento", "destinatario", "analiseAssunto", "analiseDestinatario", "analiseInfoExtra"].forEach((id) => {
    if ($(id)) $(id).value = "";
  });
  documentosDespacho = $("criarOficio").checked ? ["o {oficio}"] : [];
  mensagemEditada = false;
  analiseAtual = null;
  opcaoSelecionada = null;
  autoridadeAtual = null;
  destinatarioEditado = false;
  atualizarDespacho();
  $("geradorDespacho").classList.add("hidden");
  $("resultado").classList.add("hidden");
  $("analisePainel").classList.add("hidden");
  $("avisoDestinatario").classList.add("hidden");
  if ($("analiseAvisoDest")) $("analiseAvisoDest").classList.add("hidden");
});

$("btnCopiar").addEventListener("click", async () => {
  if (!resultadoAtual) return;
  await navigator.clipboard.writeText((resultadoAtual.paragrafos || []).join("\n\n"));
  $("btnCopiar").textContent = "Copiado!";
  setTimeout(() => ($("btnCopiar").textContent = "Copiar texto do documento"), 1500);
});

iniciar();
