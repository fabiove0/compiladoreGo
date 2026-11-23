# ============================================================
# GERADOR DE CÓDIGO PARA A MAQHIPO
# ============================================================
#
# O semântico já conferiu e ANOTOU a AST (tipos e símbolos).
# Este gerador percorre a mesma AST (um método visitar_<Nó> por nó)
# e vai acrescentando instruções numa lista. No fim, o main.py salva
# a lista em um arquivo .obj que a máquina virtual executa.
#
# Este módulo não é executado diretamente: ele é chamado pelo main.py
# (python3 main.py programa.go), que compila e executa.
#
# ------------------------------------------------------------
# COMO O PROGRAMA GERADO É MONTADO
# ------------------------------------------------------------
#
#     INPP                    inicia a máquina
#     ALME <n>                reserva as n variáveis globais
#     ...                     inicialização das globais
#     CHPR <main>             chama main
#     PARA                    fim
#     ...                     o código de cada função
#
# VARIÁVEIS
#   global: endereço fixo na pilha D        CRVL n / ARMZ n
#   local:  endereço relativo à base b      CRVF n / ARMF n
#
# FUNÇÕES
#   Quem chama:   ALME r         espaço para os r valores de retorno
#                 (argumentos)   empilha os argumentos
#                 CHPR end       chama a função
#   A função:     ENPR n         n = número de parâmetros
#                 ALME m         espaço para as variáveis locais
#                 ...
#                 RTPR n         volta para quem chamou
#
#   Dentro do frame (a partir da base b):
#       b-r .. b-1     valores de retorno
#       b .. b+n-1     parâmetros
#       b+n, b+n+1     endereço de retorno e b antigo (a VM guarda)
#       b+n+2 ..       variáveis locais
#
# BOOLEANOS: 0 é falso e 1 é verdadeiro.
 
from ast_nodes import nodes
from semantico.simbolos import (
    TIPO_INT, TIPO_FLOAT, TIPO_STRING, TIPO_BOOL, TIPO_RUNE,
    eh_untyped,
)
from gerador_codigo.instrucoes import (
    Instrucao, PENDENTE, texto_de_string, salvar_programa,
)
 
 
# ============================================================
# 1. TABELAS: operador do Go -> instrução da MaqHipo
# ============================================================
 
OPERADORES_BINARIOS = {
    "+": "SOMA", "-": "SUBT", "*": "MULT", "/": "DIVI", "%": "MODU",
    "&": "EBIT", "|": "OUBIT", "^": "XORB", "&^": "LIMP",
    "<<": "DESE", ">>": "DESD",
    "==": "CPIG", "!=": "CDES",
    "<": "CPME", ">": "CPMA", "<=": "CPMI", ">=": "CMAI",
}
 
# (o "+x" não gera nada, por isso não está aqui)
OPERADORES_UNARIOS = {
    "-": "INVE",
    "!": "NEGA",
    "^": "NBIT",
}
 
 
# ============================================================
# 2. GERADOR
# ============================================================
 
class Gerador:
    """Visitante que percorre a AST e produz a lista de instruções."""
 
    def __init__(self):
        # O array C da MaqHipo
        self.codigo = []
 
        # CHPR que ainda não sabem o endereço da função:
        # lista de (índice do CHPR, nome da função)
        self.chamadas_pendentes = []
 
        # nome da função -> endereço da primeira instrução dela
        self.enderecos_funcoes = {}
 
        # Próximos endereços livres para variáveis
        self.proximo_global = 0
        self.proximo_local = 0
 
        # Função em geração
        self.num_parametros = 0
        self.num_retornos = 0
 
        # Laços abertos (para break e continue)
        self.lacos = []
 
    def gerar(self, programa):
        """Gera o código do Programa e devolve a lista de Instrucao."""
        programa.aceitar(self)
        return self.codigo
 
    # ========================================================
    # 2.1 FUNÇÕES AUXILIARES
    # ========================================================
 
    def _emitir(self, operacao, argumento=None):
        """Acrescenta uma instrução e devolve o endereço dela."""
        self.codigo.append(Instrucao(operacao, argumento))
        return len(self.codigo) - 1
 
    def _corrigir(self, indice, destino=None):
        """
        Preenche o destino de um desvio emitido antes.
        Sem 'destino', usa o endereço da PRÓXIMA instrução.
        """
        if destino is None:
            destino = len(self.codigo)
 
        self.codigo[indice].argumento = str(destino)
 
    def _novo_endereco(self, simbolo):
        """Dá um endereço (global ou local) a uma variável nova."""
        if simbolo.global_:
            simbolo.endereco = self.proximo_global
            self.proximo_global += 1
        else:
            simbolo.endereco = self.proximo_local
            self.proximo_local += 1
 
    def _carregar(self, simbolo):
        """Empilha o valor da variável."""
        operacao = "CRVL" if simbolo.global_ else "CRVF"
        self._emitir(operacao, simbolo.endereco)
 
    def _armazenar(self, simbolo):
        """Tira o topo da pilha e guarda na variável."""
        operacao = "ARMZ" if simbolo.global_ else "ARMF"
        self._emitir(operacao, simbolo.endereco)
 
    def _guardar(self, destinos):
        """
        Os valores já estão empilhados, em ordem. O último está no
        topo, então guardamos de trás para frente. Destino None é o
        "_": o valor é só descartado.
        """
        for simbolo in reversed(destinos):
            if simbolo is None:
                self._emitir("DESM", 1)
            else:
                self._armazenar(simbolo)
 
    def _visitar_comandos(self, comandos):
        for comando in comandos:
            comando.aceitar(self)
 
    # ========================================================
    # 2.2 PROGRAMA E FUNÇÕES
    # ========================================================
 
    def visitar_Programa(self, no):
        self._emitir("INPP")
 
        # Quantas globais existem só se sabe depois de gerar as
        # declarações; por isso o ALME é corrigido no final.
        indice_globais = self._emitir("ALME", 0)
 
        for declaracao in no.declaracoes:
            if isinstance(declaracao, (nodes.DeclVar, nodes.DeclConst)):
                declaracao.aceitar(self)
 
        self.codigo[indice_globais].argumento = str(self.proximo_global)
 
        # Começa a execução: chama main e termina
        indice = self._emitir("CHPR", PENDENTE)
        self.chamadas_pendentes.append((indice, "main"))
        self._emitir("PARA")
 
        for declaracao in no.declaracoes:
            if isinstance(declaracao, nodes.DeclFuncao):
                declaracao.aceitar(self)
 
        # Agora todas as funções têm endereço: preenche os CHPR.
        # (Assim uma função pode chamar outra que vem depois dela.)
        for indice, nome in self.chamadas_pendentes:
            self._corrigir(indice, self.enderecos_funcoes[nome])
 
    def visitar_Import(self, no):
        pass  # imports não geram código
 
    def visitar_DeclFuncao(self, no):
        self.enderecos_funcoes[no.nome] = len(self.codigo)
 
        self.num_parametros = len(no.parametros)
        self.num_retornos = len(no.simbolo.assinatura.retornos)
 
        # O parâmetro i fica em b+i. As variáveis locais começam
        # depois das 2 posições que a VM usa (retorno e b antigo).
        for i, parametro in enumerate(no.parametros):
            simbolo = getattr(parametro, "simbolo", None)
 
            if simbolo is not None:
                simbolo.endereco = i
 
        self.proximo_local = self.num_parametros + 2
 
        self._emitir("ENPR", self.num_parametros)
 
        # Quantas locais existem só se sabe depois do corpo
        indice_locais = self._emitir("ALME", 0)
 
        self._visitar_comandos(no.corpo.comandos)
 
        total_locais = self.proximo_local - (self.num_parametros + 2)
        self.codigo[indice_locais].argumento = str(total_locais)
 
        # Fim da função (serve também para as que não têm return)
        self._emitir("RTPR", self.num_parametros)
 
    # ========================================================
    # 2.3 DECLARAÇÕES
    # ========================================================
 
    def _declarar(self, no):
        """var e const: guardam valores em variáveis novas."""
 
        # Sem valor: a variável começa com o valor zero do tipo
        if not no.valores:
            for simbolo in no.simbolos:
                if simbolo is None:
                    continue
 
                self._novo_endereco(simbolo)
 
                if simbolo.tipo == TIPO_FLOAT:
                    self._emitir("CRCT", "0.0")
                elif simbolo.tipo == TIPO_STRING:
                    self._emitir("CRCT", texto_de_string(""))
                else:
                    self._emitir("CRCT", 0)
 
                self._armazenar(simbolo)
            return
 
        # Com valor: empilha todos e guarda de trás para frente
        for valor in no.valores:
            valor.aceitar(self)
 
        destinos = []
 
        for simbolo in no.simbolos:
            if simbolo is not None:
                self._novo_endereco(simbolo)
 
            destinos.append(simbolo)
 
        self._guardar(destinos)
 
    def visitar_DeclVar(self, no):
        self._declarar(no)
 
    def visitar_DeclConst(self, no):
        # A constante vira uma variável comum; o semântico já
        # garantiu que ninguém escreve nela.
        self._declarar(no)
 
    # ========================================================
    # 2.4 COMANDOS
    # ========================================================
 
    def visitar_Bloco(self, no):
        self._visitar_comandos(no.comandos)
 
    def visitar_ComandoExpressao(self, no):
        no.expressao.aceitar(self)
 
        # Se a chamada devolve valores e ninguém usa, joga fora
        if no.expressao.tipos:
            self._emitir("DESM", len(no.expressao.tipos))
 
    def visitar_DeclaracaoCurta(self, no):
        # Lado direito primeiro: em "x := x + 1" o x da direita é o de fora
        for valor in no.valores:
            valor.aceitar(self)
 
        destinos = []
 
        for alvo, novo in zip(no.alvos, no.novos):
            if alvo.nome == "_":
                destinos.append(None)
                continue
 
            if novo:
                self._novo_endereco(alvo.simbolo)
 
            destinos.append(alvo.simbolo)
 
        self._guardar(destinos)
 
    def visitar_Atribuicao(self, no):
 
        # x = valor   /   a, b = b, a   /   q, r = f()
        # Todos os valores são calculados ANTES de guardar qualquer
        # um; é isso que faz "a, b = b, a" funcionar.
        if no.operador == "=":
            for valor in no.valores:
                valor.aceitar(self)
 
            destinos = []
 
            for alvo in no.alvos:
                if alvo.nome == "_":
                    destinos.append(None)
                else:
                    destinos.append(alvo.simbolo)
 
            self._guardar(destinos)
            return
 
        # x += valor (e as outras): equivale a  x = x + valor
        alvo = no.alvos[0]
 
        self._carregar(alvo.simbolo)
        no.valores[0].aceitar(self)
        self._emitir(OPERADORES_BINARIOS[no.operador[:-1]])
        self._armazenar(alvo.simbolo)
 
    def visitar_IncDec(self, no):
        # x++  equivale a  x = x + 1
        self._carregar(no.alvo.simbolo)
 
        if no.alvo.tipo == TIPO_FLOAT:
            self._emitir("CRCT", "1.0")
        else:
            self._emitir("CRCT", 1)
 
        self._emitir("SOMA" if no.operador == "++" else "SUBT")
        self._armazenar(no.alvo.simbolo)
 
    def visitar_Return(self, no):
        r = self.num_retornos
 
        for valor in no.valores:
            valor.aceitar(self)
 
        # O k-ésimo valor de retorno fica em b-r+k, ou seja, ARMF (k-r).
        # O último está no topo, então guardamos de trás para frente.
        for k in reversed(range(r)):
            self._emitir("ARMF", k - r)
 
        self._emitir("RTPR", self.num_parametros)
 
    def visitar_Break(self, no):
        indice = self._emitir("DSVI", PENDENTE)
        self.lacos[-1]["breaks"].append(indice)
 
    def visitar_Continue(self, no):
        indice = self._emitir("DSVI", PENDENTE)
        self.lacos[-1]["continues"].append(indice)
 
    def visitar_If(self, no):
        if no.inicializacao is not None:
            no.inicializacao.aceitar(self)
 
        no.condicao.aceitar(self)
 
        # Condição falsa: pula o bloco "então"
        pula_entao = self._emitir("DSVF", PENDENTE)
        no.entao.aceitar(self)
 
        if no.senao is None:
            self._corrigir(pula_entao)
            return
 
        # Ao terminar o "então", pula o "senão"
        pula_senao = self._emitir("DSVI", PENDENTE)
 
        self._corrigir(pula_entao)
        no.senao.aceitar(self)
 
        self._corrigir(pula_senao)
 
    def visitar_For(self, no):
        if no.inicializacao is not None:
            no.inicializacao.aceitar(self)
 
        inicio = len(self.codigo)
 
        # Sem condição, o laço repete para sempre (só sai com break)
        sai_do_laco = None
 
        if no.condicao is not None:
            no.condicao.aceitar(self)
            sai_do_laco = self._emitir("DSVF", PENDENTE)
 
        laco = {"breaks": [], "continues": []}
        self.lacos.append(laco)
        no.corpo.aceitar(self)
        self.lacos.pop()
 
        # "continue" vem para cá: faz o passo e testa de novo
        for indice in laco["continues"]:
            self._corrigir(indice)
 
        if no.passo is not None:
            no.passo.aceitar(self)
 
        self._emitir("DSVI", inicio)
 
        # Daqui para frente é o fim do laço
        if sai_do_laco is not None:
            self._corrigir(sai_do_laco)
 
        for indice in laco["breaks"]:
            self._corrigir(indice)
 
    # ========================================================
    # 2.5 EXPRESSÕES
    # ========================================================
    # Depois de visitada, toda expressão deixa o
    # valor dela no topo da pilha. (Uma chamada com vários retornos
    # deixa todos os valores, em ordem.)
 
    def visitar_LiteralInteiro(self, no):
        # "var f float64 = 2": o semântico deu o tipo float64 ao 2,
        # então ele entra na máquina como real (2.0).
        if no.tipo == TIPO_FLOAT:
            self._emitir("CRCT", repr(float(no.valor)))
        else:
            self._emitir("CRCT", no.valor)
 
    def visitar_LiteralReal(self, no):
        self._emitir("CRCT", repr(no.valor))
 
    def visitar_LiteralRune(self, no):
        # no.valor já é o código do caractere ('a' -> 97)
        if no.tipo == TIPO_FLOAT:
            self._emitir("CRCT", repr(float(no.valor)))
        else:
            self._emitir("CRCT", no.valor)
 
    def visitar_LiteralString(self, no):
        # no.valor já vem sem aspas e com os escapes resolvidos
        self._emitir("CRCT", texto_de_string(no.valor))
 
    def visitar_Identificador(self, no):
        simbolo = no.simbolo
 
        # true e false não têm endereço: viram 1 e 0
        if no.nome in ("true", "false") and not hasattr(simbolo, "endereco"):
            self._emitir("CRCT", 1 if no.nome == "true" else 0)
            return
 
        self._carregar(simbolo)
 
        # const n = 10 é guardada como inteiro. Se o contexto a usa
        # como float64, converte ao carregar.
        if simbolo.categoria == "const" and eh_untyped(simbolo.tipo):
            if no.tipo == TIPO_FLOAT:
                self._emitir("CONV", "float64")
 
    def visitar_Unaria(self, no):
        no.operando.aceitar(self)
 
        if no.operador in OPERADORES_UNARIOS:
            self._emitir(OPERADORES_UNARIOS[no.operador])
 
    def visitar_Binaria(self, no):
 
        # a && b: se a é falso, b nem é calculado
        if no.operador == "&&":
            no.esquerda.aceitar(self)
            falso = self._emitir("DSVF", PENDENTE)
 
            no.direita.aceitar(self)
            fim = self._emitir("DSVI", PENDENTE)
 
            self._corrigir(falso)
            self._emitir("CRCT", 0)
 
            self._corrigir(fim)
            return
 
        # a || b: se a é verdadeiro, b nem é calculado.
        # NEGA inverte a, para o DSVF (que só pula no "falso") pular
        # justamente quando a era verdadeiro.
        if no.operador == "||":
            no.esquerda.aceitar(self)
            self._emitir("NEGA")
            verdadeiro = self._emitir("DSVF", PENDENTE)
 
            no.direita.aceitar(self)
            fim = self._emitir("DSVI", PENDENTE)
 
            self._corrigir(verdadeiro)
            self._emitir("CRCT", 1)
 
            self._corrigir(fim)
            return
 
        # Os demais: calcula os dois lados e aplica o operador
        no.esquerda.aceitar(self)
        no.direita.aceitar(self)
        self._emitir(OPERADORES_BINARIOS[no.operador])
 
    # --------------------------------------------------------
    # Chamadas
    # --------------------------------------------------------
 
    def visitar_Chamada(self, no):
        if no.eh_conversao:
            self._gerar_conversao(no)
        elif no.builtin:
            self._gerar_fmt(no)
        else:
            self._gerar_chamada(no)
 
    def _gerar_conversao(self, no):
        """int(x), float64(x), string(x), rune(x)."""
        no.argumentos[0].aceitar(self)
 
        # bool(x) não precisa converter nada
        if no.funcao.nome != TIPO_BOOL:
            self._emitir("CONV", no.funcao.nome)
 
    def _gerar_chamada(self, no):
        """Chamada de uma função do próprio programa."""
        simbolo = no.funcao.simbolo
        retornos = len(simbolo.assinatura.retornos)
 
        # 1) espaço para os valores de retorno
        if retornos:
            self._emitir("ALME", retornos)
 
        # 2) argumentos
        for argumento in no.argumentos:
            argumento.aceitar(self)
 
        # 3) chamada. O endereço é preenchido no fim do programa,
        #    porque a função pode estar mais embaixo no arquivo.
        indice = self._emitir("CHPR", PENDENTE)
        self.chamadas_pendentes.append((indice, simbolo.nome))
 
    def _imprimir(self, argumento):
        """Calcula o argumento e imprime (bool vira true/false)."""
        argumento.aceitar(self)
        self._emitir("IMPB" if argumento.tipo == TIPO_BOOL else "IMPR")
 
    def _gerar_fmt(self, no):
        """fmt.Println, fmt.Print, fmt.Printf e fmt.Sprintf."""
 
        # Println: espaço entre os valores e quebra de linha no fim
        if no.builtin == "fmt.Println":
            for i, argumento in enumerate(no.argumentos):
                if i > 0:
                    self._emitir("CRCT", texto_de_string(" "))
                    self._emitir("IMPR")
 
                self._imprimir(argumento)
 
            self._emitir("QUEB")
 
        # Print: os valores um depois do outro, sem espaço e sem quebra
        elif no.builtin == "fmt.Print":
            for argumento in no.argumentos:
                self._imprimir(argumento)
 
        # Printf e Sprintf: empilha o formato e os valores; o FMT
        # monta o texto. Sprintf deixa o texto na pilha (é o valor
        # da expressão); Printf imprime.
        else:
            for argumento in no.argumentos:
                argumento.aceitar(self)
 
            self._emitir("FMT", len(no.argumentos) - 1)
 
            if no.builtin == "fmt.Printf":
                self._emitir("IMPR")
 
 
# ============================================================
# 3. FUNÇÃO DE CONVENIÊNCIA
# ============================================================
 
def gerar_codigo(programa):
    """Gera o código objeto e devolve a lista de Instrucao."""
    return Gerador().gerar(programa)
 
