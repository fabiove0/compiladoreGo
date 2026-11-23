# ============================================================
# ANALISADOR SEMÂNTICO
# ============================================================
#
# Visão geral:

#
#   Ele é um VISITANTE da AST (nodes.py): para cada nó existe um método
#   visitar_<NomeDaClasse>. Ao percorrer a árvore, ele
#
#     1) confere as regras da linguagem e junta os erros numa lista
#        (não para no primeiro: mostra todos de uma vez);
#     2) ANOTA a árvore para o gerador de código:
#          - toda expressão ganha o campo "tipo" (int, float64...);
#          - todo Identificador ganha "simbolo" (a declaração dele);
#          - Chamada ganha "tipos", "eh_conversao" e "builtin".
#

#
# O QUE É VERIFICADO
# ------------------
#   - nomes declarados antes do uso; sem redeclaração no mesmo escopo
#   - tipos em operações, atribuições, argumentos e retornos
#   - ":=" com pelo menos uma variável nova, só com identificadores
#   - condição de if/for do tipo bool
#   - comando de expressão só para chamadas
#   - break/continue só dentro de for
#   - função com retorno termina em return (como o Go exige)
#   - variável local declarada e não usada; import não usado
#   - const só com expressões constantes; atribuição a const proibida
#   - existe "func main()" sem parâmetros e sem retorno
#
# O QUE NÃO É SUPORTADO (a gramática aceita, mas aqui vira erro)
# --------------------------------------------------------------
#   - v[i] (a linguagem  não tem arrays)
#   - pacotes além de "fmt"
#   - f(g()) quando g devolve vários valores (use a, b := g(); f(a, b))
#
# Ordem de declaração: funções podem ser usadas antes de aparecerem
# no arquivo (como em Go). Variáveis e constantes GLOBAIS precisam
# aparecer antes de quem as usa na inicialização de outras globais.
 
from ast_nodes import nodes
from semantico.simbolos import (
    Assinatura, Simbolo, TabelaSimbolos,
    TIPOS_NUMERICOS,
    TIPO_INT, TIPO_STRING, TIPO_BOOL,
    TIPO_ERRO, TIPO_VOID, TIPO_BRANCO,
    UNTYPED_INT, UNTYPED_RUNE, UNTYPED_FLOAT,
    eh_untyped, eh_numerico, eh_inteiro, tipo_padrao,
    pode_converter, atribuivel, unificar, nome_tipo,
)
 
 
# ============================================================
# 1. ERRO
# ============================================================
 
class ErroSemantico:
    """Um erro semântico, com posição no código-fonte."""
 
    def __init__(self, mensagem, linha=None, coluna=None):
        self.mensagem = mensagem
        self.linha = linha
        self.coluna = coluna
 
    def __str__(self):
        if self.linha is None:
            return f"Erro semântico: {self.mensagem}"
 
        return (
            f"Erro semântico na linha {self.linha}, "
            f"coluna {self.coluna}: {self.mensagem}"
        )
 
    __repr__ = __str__
 
 
# ============================================================
# 2. ANALISADOR
# ============================================================
 
class Semantico:
    """Visitante que faz a análise semântica e anota a AST."""
 
    # Pacotes que podem ser importados e suas funções.
    # "any" = aceita argumentos de qualquer tipo.
    PACOTES = {
        "fmt": {
            "Println": Assinatura([], [], "any"),
            "Print": Assinatura([], [], "any"),
            "Printf": Assinatura([TIPO_STRING], [], "any"),
            "Sprintf": Assinatura([TIPO_STRING], [TIPO_STRING], "any"),
        }
    }
 
    def __init__(self, exigir_uso=True):
        """
        exigir_uso: se True (como o Go), variável local não usada e
        import não usado são ERROS. Com False, esses casos são
        ignorados.
        """
        self.exigir_uso = exigir_uso
 
        self.erros = []
        self.tabela = TabelaSimbolos()
 
        # Contexto da função/laço que está sendo analisado
        self.retornos_atuais = []
        self.profundidade_laco = 0
 
    # ========================================================
    # 2.1 ENTRADA
    # ========================================================
 
    def analisar(self, programa):
        """Analisa o Programa e devolve a lista de ErroSemantico."""
 
        self.erros = []
        self.tabela = TabelaSimbolos()
        self.retornos_atuais = []
        self.profundidade_laco = 0
 
        # A tabela já vem com o escopo do universo (tipos, true, false)
        # e o escopo do pacote (imports, funções e variáveis globais).
        programa.aceitar(self)
 
        self.erros.sort(key=lambda e: (e.linha or 0, e.coluna or 0))
 
        return self.erros
 
    # ========================================================
    # 2.2 FUNÇÕES AUXILIARES
    # ========================================================
 
    def _erro(self, mensagem, no=None):
        linha = getattr(no, "linha", None)
        coluna = getattr(no, "coluna", None)
        self.erros.append(ErroSemantico(mensagem, linha, coluna))
 
    def _sair_escopo(self):
        """Sai do escopo e aponta variáveis locais não usadas."""
        simbolos = self.tabela.sair_escopo()
 
        if not self.exigir_uso:
            return
 
        for simbolo in simbolos:
            if (
                simbolo.categoria == "var"
                and not simbolo.usado
                and not simbolo.global_
            ):
                self.erros.append(ErroSemantico(
                    f"variável '{simbolo.nome}' declarada e não usada",
                    simbolo.linha,
                    simbolo.coluna
                ))
 
    def _declarar(self, simbolo, no):
        """Declara o símbolo; avisa se o nome já existe neste escopo."""
        anterior = self.tabela.declarar(simbolo)
 
        if anterior is not None:
            onde = ""
            if anterior.linha is not None:
                onde = f" (linha {anterior.linha})"
 
            self._erro(
                f"'{simbolo.nome}' já foi declarado neste escopo{onde}",
                no
            )
 
        return simbolo
 
    def _resolver_tipo(self, no_tipo):
        """Tipo (nó) -> nome do tipo, ou TIPO_ERRO se não existir."""
        simbolo = self.tabela.buscar(no_tipo.nome)
 
        if simbolo is None or simbolo.categoria != "tipo":
            self._erro(f"o tipo '{no_tipo.nome}' não existe", no_tipo)
            return TIPO_ERRO
 
        return simbolo.nome
 
    def _visitar_comandos(self, comandos):
        for comando in comandos:
            comando.aceitar(self)
 
    # ========================================================
    # 2.3 TIPOS: conversão e verificação
    # ========================================================
 
    def _fixar_tipo(self, no, alvo):
        """
        Dá um tipo concreto a uma expressão que ainda é constante sem
        tipo. A mudança desce pela árvore:  2.5 * 2  com alvo float64
        deixa os DOIS literais como float64.
        """
        if not eh_untyped(no.tipo):
            return
 
        no.tipo = alvo
 
        if isinstance(no, nodes.Unaria):
            self._fixar_tipo(no.operando, alvo)
 
        elif isinstance(no, nodes.Binaria):
            self._fixar_tipo(no.esquerda, alvo)
 
            # Em x << n, o tipo do resultado é o de x, não o de n.
            if no.operador not in ("<<", ">>"):
                self._fixar_tipo(no.direita, alvo)
 
    def _fixar_padrao(self, no):
        """Constante sem tipo e sem contexto: vira int, float64 ou rune."""
        if eh_untyped(no.tipo):
            self._fixar_tipo(no, tipo_padrao(no.tipo))
 
    def _checar_atribuicao(self, tipo_origem, no_origem, tipo_alvo,
                           no_erro, contexto):
        """
        Confere se um valor cabe no tipo de destino. Se couber, e o
        valor for constante sem tipo, fixa o tipo dela.
 
        no_origem pode ser None (valor vindo de uma chamada com vários
        retornos: não há nó individual para ajustar).
        """
        if TIPO_ERRO in (tipo_origem, tipo_alvo):
            return
 
        if atribuivel(tipo_origem, tipo_alvo):
            if no_origem is not None:
                self._fixar_tipo(no_origem, tipo_alvo)
            return
 
        # Aponta para o próprio valor quando ele existe (como o Go).
        self._erro(
            f"não é possível usar {nome_tipo(tipo_origem)} "
            f"como {tipo_alvo} em {contexto}",
            no_origem if no_origem is not None else no_erro
        )
 
    def _valor_unico(self, no):
        """
        Visita uma expressão que precisa produzir EXATAMENTE um valor
        e devolve o tipo dela. Chamadas sem retorno ou com vários
        retornos são erro aqui.
        """
        no.aceitar(self)
        tipo = no.tipo
 
        if tipo == TIPO_VOID:
            self._erro("esta chamada não devolve valor", no)
            no.tipo = TIPO_ERRO
 
        elif isinstance(tipo, tuple):
            self._erro(
                f"esta chamada devolve {len(tipo)} valores, "
                "mas um só é esperado aqui",
                no
            )
            no.tipo = TIPO_ERRO
 
        return no.tipo
 
    def _avaliar_lista(self, valores, quantidade, no_ref, contexto):
        """
        Visita a lista de valores de uma atribuição/declaração/return
        e devolve [(tipo, no), ...] com 'quantidade' itens.
 
        Aceita o caso especial de UMA chamada que devolve vários valores:
            a, b := divmod(7, 2)      -> [(int, None), (int, None)]
        (o nó é None porque o valor não tem expressão própria).
        """
        if len(valores) == 1 and quantidade > 1:
            valor = valores[0]
            valor.aceitar(self)
 
            if isinstance(valor.tipo, tuple):
                if len(valor.tipo) == quantidade:
                    return [(tipo, None) for tipo in valor.tipo]
 
                self._erro(
                    f"{contexto}: esperado {quantidade} valores, "
                    f"mas a chamada devolve {len(valor.tipo)}",
                    valor
                )
 
            elif valor.tipo != TIPO_ERRO:
                self._erro(
                    f"{contexto}: esperado {quantidade} valores, "
                    "recebido 1",
                    valor
                )
 
            return [(TIPO_ERRO, None)] * quantidade
 
        tipos = [self._valor_unico(valor) for valor in valores]
 
        if len(valores) != quantidade:
            self._erro(
                f"{contexto}: esperado {quantidade} valor(es), "
                f"recebido {len(valores)}",
                no_ref
            )
            return [(TIPO_ERRO, None)] * quantidade
 
        return list(zip(tipos, valores))
 
    # ========================================================
    # 2.4 PROGRAMA, IMPORTS E FUNÇÕES
    # ========================================================
 
    def visitar_Programa(self, no):
 
        # Imports
        for importacao in no.imports:
            importacao.aceitar(self)
 
        # Passo 1: assinaturas de TODAS as funções. Assim uma função
        # pode chamar outra que aparece mais embaixo no arquivo.
        for declaracao in no.declaracoes:
            if isinstance(declaracao, nodes.DeclFuncao):
                self._declarar_assinatura(declaracao)
 
        # Passo 2: variáveis e constantes globais, na ordem do arquivo.
        for declaracao in no.declaracoes:
            if isinstance(declaracao, (nodes.DeclVar, nodes.DeclConst)):
                declaracao.aceitar(self)
 
        # Passo 3: corpo das funções.
        for declaracao in no.declaracoes:
            if isinstance(declaracao, nodes.DeclFuncao):
                declaracao.aceitar(self)
 
        self._conferir_main(no)
 
        # Imports não usados
        if self.exigir_uso:
            for simbolo in self.tabela.escopos[-1].values():
                if simbolo.categoria == "pacote" and not simbolo.usado:
                    self.erros.append(ErroSemantico(
                        f"pacote '{simbolo.tipo}' importado "
                        "e não utilizado",
                        simbolo.linha,
                        simbolo.coluna
                    ))
 
    def visitar_Import(self, no):
        if no.caminho not in self.PACOTES:
            suportados = ", ".join(sorted(self.PACOTES))
            self._erro(
                f"pacote '{no.caminho}' não é suportado "
                f"(disponível: {suportados})",
                no
            )
            return
 
        nome = no.apelido if no.apelido else no.caminho
 
        if nome == "_":
            return
 
        simbolo = Simbolo(nome, "pacote", no.caminho, no.linha, no.coluna)
        self._declarar(simbolo, no)
 
    def _declarar_assinatura(self, no):
        """Passo 1: cria o símbolo da função com seus tipos."""
        parametros = [self._resolver_tipo(p.tipo) for p in no.parametros]
        retornos = [self._resolver_tipo(t) for t in no.tipos_retorno]
 
        simbolo = Simbolo(
            no.nome, "func",
            linha=no.linha, coluna=no.coluna,
            assinatura=Assinatura(parametros, retornos),
            global_=True
        )
        simbolo.usado = True
 
        no.simbolo = simbolo
        self._declarar(simbolo, no)
 
    def _conferir_main(self, programa):
        simbolo = self.tabela.buscar_local("main")
 
        if simbolo is None or simbolo.categoria != "func":
            self._erro("função 'main' não foi declarada", programa)
            return
 
        assinatura = simbolo.assinatura
 
        if assinatura.parametros or assinatura.retornos:
            self.erros.append(ErroSemantico(
                "a função 'main' não pode ter parâmetros nem retorno",
                simbolo.linha,
                simbolo.coluna
            ))
 
    def visitar_DeclFuncao(self, no):
        """Passo 3: confere o corpo da função."""
        assinatura = no.simbolo.assinatura
 
        self.retornos_atuais = assinatura.retornos
        self.profundidade_laco = 0
 
        # Os parâmetros ficam no MESMO escopo do corpo da função:
        # redeclarar um parâmetro dentro do corpo é erro, como em Go.
        self.tabela.entrar_escopo()
 
        for parametro, tipo in zip(no.parametros, assinatura.parametros):
            if parametro.nome == "_":
                continue
 
            simbolo = Simbolo(
                parametro.nome, "var", tipo,
                parametro.linha, parametro.coluna
            )
            simbolo.usado = True  # parâmetro não usado é permitido
 
            parametro.simbolo = simbolo
            self._declarar(simbolo, parametro)
 
        self._visitar_comandos(no.corpo.comandos)
 
        self._sair_escopo()
 
        if assinatura.retornos and not self._termina(no.corpo):
            self._erro(
                f"a função '{no.nome}' pode terminar sem um return",
                no
            )
 
    # ========================================================
    # 2.5 "ESTA SEQUÊNCIA DE COMANDOS TERMINA EM RETURN?"
    # ========================================================
    # Regra do Go: uma função com retorno precisa terminar em um
    # "comando terminal":
    #   - return
    #   - bloco cujo último comando é terminal
    #   - if COM else, em que os dois lados são terminais
    #   - for sem condição e sem break
 
    def _termina(self, comando):
        if isinstance(comando, nodes.Return):
            return True
 
        if isinstance(comando, nodes.Bloco):
            return bool(comando.comandos) and self._termina(
                comando.comandos[-1]
            )
 
        if isinstance(comando, nodes.If):
            return (
                comando.senao is not None
                and self._termina(comando.entao)
                and self._termina(comando.senao)
            )
 
        if isinstance(comando, nodes.For):
            return (
                comando.condicao is None
                and not self._tem_break(comando.corpo)
            )
 
        return False
 
    def _tem_break(self, comando):
        """Há um break que sai do laço atual? (ignora laços internos)"""
        if isinstance(comando, nodes.Break):
            return True
 
        if isinstance(comando, nodes.Bloco):
            return any(self._tem_break(c) for c in comando.comandos)
 
        if isinstance(comando, nodes.If):
            return self._tem_break(comando.entao) or (
                comando.senao is not None
                and self._tem_break(comando.senao)
            )
 
        return False
 
    # ========================================================
    # 2.6 VARIÁVEIS E CONSTANTES
    # ========================================================
 
    def _simbolo_de_variavel(self, nome, tipo, no):
        """Declara uma variável no escopo atual (None para "_")."""
        if nome == "_":
            return None
 
        simbolo = Simbolo(
            nome, "var", tipo, no.linha, no.coluna,
            global_=self.tabela.no_escopo_do_pacote
        )
 
        self._declarar(simbolo, no)
        return simbolo
 
    def visitar_DeclVar(self, no):
        tipo_declarado = None
        if no.tipo is not None:
            tipo_declarado = self._resolver_tipo(no.tipo)
 
        # Os valores são analisados ANTES de declarar os nomes:
        # em "var x = x" o segundo x é o de fora.
        pares = None
        if no.valores:
            pares = self._avaliar_lista(
                no.valores, len(no.nomes), no, "declaração"
            )
 
        no.simbolos = []
 
        for i, nome in enumerate(no.nomes):
 
            if tipo_declarado is not None:
                tipo = tipo_declarado
 
                if pares is not None:
                    tipo_valor, valor = pares[i]
                    self._checar_atribuicao(
                        tipo_valor, valor, tipo, no, "declaração"
                    )
 
            else:
                tipo_valor, valor = pares[i]
                tipo = tipo_padrao(tipo_valor)
 
                if valor is not None:
                    self._fixar_padrao(valor)
 
            no.simbolos.append(self._simbolo_de_variavel(nome, tipo, no))
 
    def visitar_DeclConst(self, no):
        tipo_declarado = None
        if no.tipo is not None:
            tipo_declarado = self._resolver_tipo(no.tipo)
 
        pares = self._avaliar_lista(
            no.valores, len(no.nomes), no, "declaração"
        )
 
        # Constante só aceita expressão constante (não vale chamar função)
        for valor in no.valores:
            if valor.tipo != TIPO_ERRO and not self._eh_constante(valor):
                self._erro(
                    "o valor de uma constante deve ser uma expressão "
                    "constante",
                    valor
                )
 
        no.simbolos = []
 
        for i, nome in enumerate(no.nomes):
            tipo_valor, valor = pares[i]
 
            if tipo_declarado is not None:
                tipo = tipo_declarado
                self._checar_atribuicao(
                    tipo_valor, valor, tipo, no, "declaração de constante"
                )
            else:
                # Sem tipo declarado, a constante continua "sem tipo":
                # const n = 10 serve tanto para int quanto para float64.
                tipo = tipo_valor
 
            simbolo = Simbolo(
                nome, "const", tipo, no.linha, no.coluna,
                global_=self.tabela.no_escopo_do_pacote
            )
            simbolo.usado = True
 
            if nome != "_":
                self._declarar(simbolo, no)
 
            no.simbolos.append(simbolo)
 
    def _eh_constante(self, no):
        if isinstance(no, (nodes.LiteralInteiro, nodes.LiteralReal,
                           nodes.LiteralString, nodes.LiteralRune)):
            return True
 
        if isinstance(no, nodes.Identificador):
            return no.simbolo is not None and no.simbolo.categoria == "const"
 
        if isinstance(no, nodes.Unaria):
            return self._eh_constante(no.operando)
 
        if isinstance(no, nodes.Binaria):
            return (
                self._eh_constante(no.esquerda)
                and self._eh_constante(no.direita)
            )
 
        if isinstance(no, nodes.Chamada):
            return no.eh_conversao and all(
                self._eh_constante(a) for a in no.argumentos
            )
 
        return False
 
    # ========================================================
    # 2.7 COMANDOS
    # ========================================================
 
    def visitar_Bloco(self, no):
        self.tabela.entrar_escopo()
        self._visitar_comandos(no.comandos)
        self._sair_escopo()
 
    def visitar_ComandoExpressao(self, no):
        no.expressao.aceitar(self)
 
        if not isinstance(no.expressao, nodes.Chamada):
            self._erro(
                "esta expressão não pode ser usada como comando "
                "(só chamadas de função)",
                no
            )
 
        elif no.expressao.eh_conversao:
            self._erro(
                "o resultado de uma conversão não pode ser descartado",
                no
            )
 
    def visitar_DeclaracaoCurta(self, no):
        # Lado direito primeiro: em "x := x + 1" o x da direita é o de fora.
        pares = self._avaliar_lista(
            no.valores, len(no.alvos), no, "declaração curta"
        )
 
        no.novos = []
        nomes_vistos = set()
        criou_variavel = False
        houve_erro_no_alvo = False
 
        for alvo, (tipo_valor, valor) in zip(no.alvos, pares):
 
            if not isinstance(alvo, nodes.Identificador):
                self._erro(
                    "o lado esquerdo de ':=' deve conter só nomes de "
                    "variáveis",
                    alvo
                )
                houve_erro_no_alvo = True
                no.novos.append(False)
                continue
 
            # "_" descarta o valor
            if alvo.nome == "_":
                if valor is not None:
                    self._fixar_padrao(valor)
                no.novos.append(False)
                continue
 
            if alvo.nome in nomes_vistos:
                self._erro(
                    f"'{alvo.nome}' aparece mais de uma vez no lado "
                    "esquerdo de ':='",
                    alvo
                )
                houve_erro_no_alvo = True
                no.novos.append(False)
                continue
 
            nomes_vistos.add(alvo.nome)
 
            existente = self.tabela.buscar_local(alvo.nome)
 
            if existente is None:
                # Variável nova: o tipo vem do valor.
                tipo = tipo_padrao(tipo_valor)
 
                simbolo = Simbolo(
                    alvo.nome, "var", tipo, alvo.linha, alvo.coluna,
                    global_=False
                )
                self.tabela.declarar(simbolo)
 
                alvo.simbolo = simbolo
                alvo.tipo = tipo
 
                if valor is not None:
                    self._fixar_padrao(valor)
 
                criou_variavel = True
                no.novos.append(True)
 
            elif existente.categoria != "var":
                self._erro(
                    f"não é possível atribuir a '{alvo.nome}'",
                    alvo
                )
                houve_erro_no_alvo = True
                no.novos.append(False)
 
            else:
                # Já existe neste escopo: é só uma atribuição.
                alvo.simbolo = existente
                alvo.tipo = existente.tipo
 
                self._checar_atribuicao(
                    tipo_valor, valor, existente.tipo, alvo, "atribuição"
                )
                no.novos.append(False)
 
        if not criou_variavel and not houve_erro_no_alvo:
            self._erro("nenhuma variável nova no lado esquerdo de ':='", no)
 
    def _tipo_do_alvo(self, alvo, conta_como_uso=False):
        """
        Confere se 'alvo' pode receber um valor e devolve o tipo dele
        (TIPO_BRANCO para "_").
 
        Em Go, só ESCREVER em x ("x = 1") não evita o erro "declarado e
        não usado". Já "x++" e "x += 1" também LEEM x, então contam
        como uso: quem chama esses casos passa conta_como_uso=True.
        """
        if isinstance(alvo, nodes.Identificador):
 
            if alvo.nome == "_":
                return TIPO_BRANCO
 
            simbolo = self.tabela.buscar(alvo.nome)
 
            if simbolo is None:
                self._erro(f"'{alvo.nome}' não foi declarado", alvo)
                return TIPO_ERRO
 
            if simbolo.categoria != "var":
                tipo_simbolo = {
                    "const": "uma constante",
                    "func": "uma função",
                    "pacote": "um pacote",
                    "tipo": "um tipo",
                }[simbolo.categoria]
 
                self._erro(
                    f"não é possível atribuir a '{alvo.nome}': "
                    f"é {tipo_simbolo}",
                    alvo
                )
                return TIPO_ERRO
 
            if conta_como_uso:
                simbolo.usado = True
 
            alvo.simbolo = simbolo
            alvo.tipo = simbolo.tipo
            return simbolo.tipo
 
        alvo.aceitar(self)
        self._erro("não é possível atribuir a esta expressão", alvo)
        return TIPO_ERRO
 
    def visitar_Atribuicao(self, no):
        simples = no.operador == "="
 
        # --- x = valor   /   a, b = b, a   /   q, r = f() ---
        if simples:
            pares = self._avaliar_lista(
                no.valores, len(no.alvos), no, "atribuição"
            )
 
            for alvo, (tipo_valor, valor) in zip(no.alvos, pares):
                tipo_alvo = self._tipo_do_alvo(alvo)
 
                if tipo_alvo == TIPO_BRANCO:
                    if valor is not None:
                        self._fixar_padrao(valor)
                    continue
 
                self._checar_atribuicao(
                    tipo_valor, valor, tipo_alvo, alvo, "atribuição"
                )
            return
 
        # --- x += valor (e as outras compostas) ---
        if len(no.alvos) != 1 or len(no.valores) != 1:
            for valor in no.valores:
                valor.aceitar(self)
 
            self._erro(
                f"'{no.operador}' exige exatamente um alvo e um valor",
                no
            )
            return
 
        alvo = no.alvos[0]
        valor = no.valores[0]
 
        tipo_alvo = self._tipo_do_alvo(alvo, conta_como_uso=True)
        tipo_valor = self._valor_unico(valor)
 
        if tipo_alvo == TIPO_BRANCO:
            self._erro("'_' não pode ser usado em atribuição composta", alvo)
            return
 
        if TIPO_ERRO in (tipo_alvo, tipo_valor):
            return
 
        # x op= y   equivale a   x = x op y
        operador = no.operador[:-1]
        resultado = self._tipo_da_operacao(
            operador, tipo_alvo, tipo_valor, alvo, valor, no
        )
 
        if resultado != TIPO_ERRO:
            self._checar_atribuicao(
                resultado, None, tipo_alvo, no, "atribuição composta"
            )
 
    def visitar_IncDec(self, no):
        tipo = self._tipo_do_alvo(no.alvo, conta_como_uso=True)
 
        if tipo == TIPO_BRANCO:
            self._erro("'_' não pode ser usado com ++ ou --", no)
 
        elif tipo != TIPO_ERRO and not eh_numerico(tipo):
            self._erro(
                f"o operador {no.operador} exige um valor numérico, "
                f"mas recebeu {nome_tipo(tipo)}",
                no
            )
 
    def visitar_Return(self, no):
        retornos = self.retornos_atuais
 
        if not no.valores:
            if retornos:
                self._erro(
                    f"faltam valores de retorno (esperado {len(retornos)})",
                    no
                )
            return
 
        if not retornos:
            for valor in no.valores:
                valor.aceitar(self)
 
            self._erro("esta função não devolve valores", no)
            return
 
        pares = self._avaliar_lista(
            no.valores, len(retornos), no, "retorno"
        )
 
        for (tipo_valor, valor), tipo_esperado in zip(pares, retornos):
            self._checar_atribuicao(
                tipo_valor, valor, tipo_esperado, no, "retorno"
            )
 
    def visitar_Break(self, no):
        if self.profundidade_laco == 0:
            self._erro("'break' fora de um laço for", no)
 
    def visitar_Continue(self, no):
        if self.profundidade_laco == 0:
            self._erro("'continue' fora de um laço for", no)
 
    def _exigir_bool(self, condicao, comando):
        tipo = self._valor_unico(condicao)
 
        if tipo not in (TIPO_ERRO, TIPO_BOOL):
            self._erro(
                f"a condição do {comando} deve ser bool, "
                f"mas é {nome_tipo(tipo)}",
                condicao
            )
 
    def visitar_If(self, no):
        # O escopo do if cobre inicialização, condição e todos os else.
        self.tabela.entrar_escopo()
 
        if no.inicializacao is not None:
            no.inicializacao.aceitar(self)
 
        self._exigir_bool(no.condicao, "if")
 
        no.entao.aceitar(self)
 
        if no.senao is not None:
            no.senao.aceitar(self)
 
        self._sair_escopo()
 
    def visitar_For(self, no):
        self.tabela.entrar_escopo()
 
        if no.inicializacao is not None:
            no.inicializacao.aceitar(self)
 
        if no.condicao is not None:
            self._exigir_bool(no.condicao, "for")
 
        if no.passo is not None:
            no.passo.aceitar(self)
 
        self.profundidade_laco += 1
        no.corpo.aceitar(self)
        self.profundidade_laco -= 1
 
        self._sair_escopo()
 
    # ========================================================
    # 2.8 EXPRESSÕES
    # ========================================================
 
    def visitar_LiteralInteiro(self, no):
        no.tipo = UNTYPED_INT
 
    def visitar_LiteralReal(self, no):
        no.tipo = UNTYPED_FLOAT
 
    def visitar_LiteralRune(self, no):
        no.tipo = UNTYPED_RUNE
 
    def visitar_LiteralString(self, no):
        no.tipo = TIPO_STRING
 
    def visitar_Identificador(self, no):
        simbolo = self.tabela.buscar(no.nome)
        no.tipo = TIPO_ERRO
 
        if no.nome == "_":
            self._erro("'_' não pode ser usado como valor", no)
 
        elif simbolo is None:
            self._erro(f"'{no.nome}' não foi declarado", no)
 
        elif simbolo.categoria == "tipo":
            self._erro(f"'{no.nome}' é um tipo, não um valor", no)
 
        elif simbolo.categoria == "pacote":
            simbolo.usado = True
            self._erro(f"o pacote '{no.nome}' não pode ser usado como valor",
                       no)
 
        elif simbolo.categoria == "func":
            self._erro(
                f"a função '{no.nome}' só pode ser usada em chamadas",
                no
            )
 
        else:
            simbolo.usado = True
            no.simbolo = simbolo
            no.tipo = simbolo.tipo
 
    def visitar_Unaria(self, no):
        tipo = self._valor_unico(no.operando)
        no.tipo = TIPO_ERRO
 
        if tipo == TIPO_ERRO:
            return
 
        if no.operador in ("+", "-"):
            ok = eh_numerico(tipo)
        elif no.operador == "!":
            ok = tipo == TIPO_BOOL
        else:  # "^"
            ok = eh_inteiro(tipo)
 
        if not ok:
            self._erro(
                f"o operador {no.operador} não se aplica a "
                f"{nome_tipo(tipo)}",
                no
            )
            return
 
        no.tipo = tipo
 
    def visitar_Binaria(self, no):
        tipo_esquerda = self._valor_unico(no.esquerda)
        tipo_direita = self._valor_unico(no.direita)
 
        no.tipo = self._tipo_da_operacao(
            no.operador, tipo_esquerda, tipo_direita,
            no.esquerda, no.direita, no
        )
 
    def _tipo_da_operacao(self, operador, te, td, esquerda, direita, no):
        """
        Tipo do resultado de  esquerda <operador> direita  (ou TIPO_ERRO).
        Também fixa o tipo das constantes sem tipo envolvidas.
        """
        if TIPO_ERRO in (te, td):
            return TIPO_ERRO
 
        # ---- && ||  (só bool) ----
        if operador in ("&&", "||"):
            if te != TIPO_BOOL or td != TIPO_BOOL:
                self._erro(
                    f"o operador {operador} exige operandos bool, "
                    f"mas recebeu {nome_tipo(te)} e {nome_tipo(td)}",
                    no
                )
                return TIPO_ERRO
 
            return TIPO_BOOL
 
        # ---- << >>  (os tipos dos dois lados não precisam ser iguais) ----
        if operador in ("<<", ">>"):
            if not eh_inteiro(te) or not eh_inteiro(td):
                self._erro(
                    f"o operador {operador} exige operandos inteiros, "
                    f"mas recebeu {nome_tipo(te)} e {nome_tipo(td)}",
                    no
                )
                return TIPO_ERRO
 
            self._fixar_padrao(direita)
            return te
 
        # ---- demais operadores: os dois lados precisam combinar ----
        comum = unificar(te, td)
 
        if comum is None:
            self._erro(
                f"tipos incompatíveis para {operador}: "
                f"{nome_tipo(te)} e {nome_tipo(td)}",
                no
            )
            return TIPO_ERRO
 
        # Comparações: o resultado é sempre bool
        if operador in ("==", "!=", "<", "<=", ">", ">="):
 
            if operador not in ("==", "!=") and not (
                eh_numerico(comum) or comum == TIPO_STRING
            ):
                self._erro(
                    f"o operador {operador} não se aplica a "
                    f"{nome_tipo(comum)}",
                    no
                )
                return TIPO_ERRO
 
            comum = tipo_padrao(comum)
            self._fixar_tipo(esquerda, comum)
            self._fixar_tipo(direita, comum)
            return TIPO_BOOL
 
        # Aritméticos e bit a bit
        if operador == "+":
            ok = eh_numerico(comum) or comum == TIPO_STRING
        elif operador in ("-", "*", "/"):
            ok = eh_numerico(comum)
        else:  # % & | ^ &^
            ok = eh_inteiro(comum)
 
        if not ok:
            self._erro(
                f"o operador {operador} não se aplica a {nome_tipo(comum)}",
                no
            )
            return TIPO_ERRO
 
        if operador in ("/", "%") and eh_inteiro(comum):
            if (
                isinstance(direita, nodes.LiteralInteiro)
                and direita.valor == 0
            ):
                self._erro("divisão por zero", no)
                return TIPO_ERRO
 
        # Se o tipo já é concreto, as constantes dos lados viram esse tipo.
        # Se ainda é "sem tipo", o contexto (atribuição, argumento...)
        # decide depois, e _fixar_tipo desce pela árvore.
        if not eh_untyped(comum):
            self._fixar_tipo(esquerda, comum)
            self._fixar_tipo(direita, comum)
 
        return comum
 
    # --------------------------------------------------------
    # Chamadas, conversões e acessos
    # --------------------------------------------------------
 
    def _definir_resultado(self, no, tipos):
        """Preenche tipo/tipos de uma Chamada. None = deu erro."""
        if tipos is None:
            no.tipos = []
            no.tipo = TIPO_ERRO
            return
 
        no.tipos = tipos
 
        if not tipos:
            no.tipo = TIPO_VOID
        elif len(tipos) == 1:
            no.tipo = tipos[0]
        else:
            no.tipo = tuple(tipos)
 
    def visitar_Chamada(self, no):
        funcao = no.funcao
        assinatura = None
        nome = "?"
 
        if isinstance(funcao, nodes.Identificador):
            nome = funcao.nome
            simbolo = self.tabela.buscar(nome)
 
            if simbolo is None:
                self._erro(f"a função '{nome}' não foi declarada", funcao)
 
            elif simbolo.categoria == "tipo":
                self._conversao(no, simbolo)
                return
 
            elif simbolo.categoria == "func":
                simbolo.usado = True
                funcao.simbolo = simbolo
                assinatura = simbolo.assinatura
 
            else:
                simbolo.usado = True
                self._erro(f"'{nome}' não é uma função", funcao)
 
        elif (
            isinstance(funcao, nodes.AcessoMembro)
            and isinstance(funcao.objeto, nodes.Identificador)
        ):
            objeto = funcao.objeto
            simbolo = self.tabela.buscar(objeto.nome)
            nome = f"{objeto.nome}.{funcao.membro}"
 
            if simbolo is None:
                self._erro(f"'{objeto.nome}' não foi declarado", objeto)
 
            elif simbolo.categoria != "pacote":
                simbolo.usado = True
                self._erro(
                    f"'{objeto.nome}' não é um pacote "
                    "(métodos não são suportados)",
                    objeto
                )
 
            else:
                simbolo.usado = True
                objeto.simbolo = simbolo
                assinatura = self.PACOTES[simbolo.tipo].get(funcao.membro)
 
                if assinatura is None:
                    self._erro(
                        f"o pacote '{simbolo.tipo}' não possui "
                        f"'{funcao.membro}'",
                        funcao
                    )
                else:
                    no.builtin = f"{simbolo.tipo}.{funcao.membro}"
 
        else:
            self._erro("esta expressão não pode ser chamada", no)
 
        # Em caso de erro, os argumentos ainda são analisados para
        # que erros dentro deles também apareçam.
        if assinatura is None:
            for argumento in no.argumentos:
                argumento.aceitar(self)
 
            self._definir_resultado(no, None)
            return
 
        self._conferir_argumentos(no, nome, assinatura)
        self._definir_resultado(no, list(assinatura.retornos))
 
    def _conferir_argumentos(self, no, nome, assinatura):
        argumentos = no.argumentos
        parametros = assinatura.parametros
        quantidade = len(argumentos)
 
        tipos = [self._valor_unico(a) for a in argumentos]
 
        if assinatura.variadico is None:
            quantidade_ok = quantidade == len(parametros)
            esperado = f"{len(parametros)}"
        else:
            quantidade_ok = quantidade >= len(parametros)
            esperado = f"pelo menos {len(parametros)}"
 
        if not quantidade_ok:
            self._erro(
                f"a chamada de '{nome}' tem {quantidade} argumento(s), "
                f"esperado {esperado}",
                no
            )
            return
 
        for i, (argumento, tipo) in enumerate(zip(argumentos, tipos)):
            if i < len(parametros):
                self._checar_atribuicao(
                    tipo, argumento, parametros[i], argumento,
                    f"argumento {i + 1} de '{nome}'"
                )
            else:
                # Parte variádica ("any"): vale qualquer tipo.
                self._fixar_padrao(argumento)
 
    def _conversao(self, no, simbolo_tipo):
        """int(x), float64(x), string(x), bool(x), rune(x)."""
        alvo = simbolo_tipo.nome
 
        no.eh_conversao = True
        no.funcao.simbolo = simbolo_tipo
 
        if len(no.argumentos) != 1:
            for argumento in no.argumentos:
                argumento.aceitar(self)
 
            self._erro(
                f"a conversão para {alvo} exige exatamente 1 argumento",
                no
            )
            self._definir_resultado(no, None)
            return
 
        argumento = no.argumentos[0]
        tipo = self._valor_unico(argumento)
 
        if tipo == TIPO_ERRO:
            self._definir_resultado(no, None)
            return
 
        if alvo in TIPOS_NUMERICOS:
            permitido = eh_numerico(tipo)
        elif alvo == TIPO_STRING:
            # string(x) com inteiro dá o caractere de código x
            permitido = tipo == TIPO_STRING or eh_inteiro(tipo)
        else:
            permitido = tipo == alvo
 
        # Conversão inválida: a expressão fica com TIPO_ERRO (como o Go
        # faz), para que ela não pareça ter um tipo válido na AST e para
        # não gerar erros em cascata nos comandos seguintes.
        if not permitido:
            self._erro(
                f"não é possível converter {nome_tipo(tipo)} para {alvo}",
                no
            )
            self._definir_resultado(no, None)
            return
 
        if (
            alvo in ("int", "rune")
            and isinstance(argumento, nodes.LiteralReal)
            and not float(argumento.valor).is_integer()
        ):
            # Como em Go: int(2.5) é erro (o valor seria truncado).
            # Só conferimos literais; int(1.5 * 2) passa.
            self._erro(
                f"a constante {argumento.texto} seria truncada "
                f"ao converter para {alvo}",
                no
            )
            self._definir_resultado(no, None)
            return
 
        if eh_untyped(tipo):
            if pode_converter(tipo, alvo):
                self._fixar_tipo(argumento, alvo)
            else:
                self._fixar_padrao(argumento)
 
        self._definir_resultado(no, [alvo])
 
    def visitar_AcessoMembro(self, no):
        no.tipo = TIPO_ERRO
 
        if isinstance(no.objeto, nodes.Identificador):
            simbolo = self.tabela.buscar(no.objeto.nome)
 
            if simbolo is not None and simbolo.categoria == "pacote":
                simbolo.usado = True
 
        self._erro(
            "acesso com '.' só é suportado em chamadas de pacotes, "
            "como fmt.Println(...)",
            no
        )
 
    def visitar_Indexacao(self, no):
        # Os filhos são visitados para contar como "uso" das variáveis
        # (e para aparecerem erros dentro deles).
        no.objeto.aceitar(self)
        no.indice.aceitar(self)
 
        no.tipo = TIPO_ERRO
 
        self._erro(
            "indexação com [] ainda não é suportada "
            "(a linguagem não tem arrays)",
            no
        )
 
 
# ============================================================
# 3. FUNÇÃO DE CONVENIÊNCIA
# ============================================================
 
def analisar_semantica(programa, exigir_uso=True):
    """Analisa o Programa e devolve a lista de erros semânticos."""
    return Semantico(exigir_uso).analisar(programa)
 
 