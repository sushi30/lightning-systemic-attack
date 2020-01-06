from typing import TextIO

from commands_generator.config_constants import (
    CLIGHTNING_BINARY,
    CLIGHTNING_BINARY_EVIL,
    CLIGHTNING_CONF_PATH,
    INITIAL_CHANNEL_BALANCE_SAT,
)
from commands_generator.lightning import LightningCommandsGenerator
from datatypes import NodeIndex

CLOSE_CHANNEL_TIMEOUT_SEC = 60


class ClightningCommandsGenerator(LightningCommandsGenerator):
    
    def __init__(
        self,
        idx: NodeIndex,
        file: TextIO,
        lightning_dir: str,
        listen_port: int,
        bitcoin_rpc_port: int,
        alias: str = None,
        evil: bool = False,
        silent: bool = False,
    ) -> None:
        super().__init__(index=idx, file=file)
        self.lightning_dir = lightning_dir
        self.alias = alias
        self.evil = evil
        self.silent = silent
        self.listen_port = listen_port
        self.bitcoin_rpc_port = bitcoin_rpc_port
    
    def start(self) -> None:
        self._write_line(f"mkdir -p {self.lightning_dir}")
        
        binary = CLIGHTNING_BINARY
        log_level = ""
        if self.evil or self.silent:
            binary = CLIGHTNING_BINARY_EVIL
            log_level = "JONA"
        
        alias_flag = f"--alias={self.alias}" if self.alias else ""
        evil_flag = "--evil" if self.evil else ""
        silent_flag = "--silent" if self.silent else ""
        log_level_flag = f"--log-level={log_level}" if log_level else ""
        
        self._write_line(
            f"{binary} "
            f"  --conf={CLIGHTNING_CONF_PATH}"
            f"  --lightning-dir={self.lightning_dir}"
            f"  --addr=localhost:{self.listen_port}"
            f"  --log-file=log"  # relative to lightning-dir
            f"  {alias_flag}"
            f"  {evil_flag}"
            f"  {silent_flag}"
            f"  {log_level_flag}"
            f"  --bitcoin-rpcconnect=localhost"
            f"  --bitcoin-rpcport={self.bitcoin_rpc_port}"
            f"  --daemon"
        )
    
    def stop(self) -> None:
        self._write_line(f"lcli {self.idx} stop")
    
    def set_address(self, bash_var: str) -> None:
        self._write_line(f"{bash_var}=$(lcli {self.idx} newaddr | jq -r '.address')")
    
    def set_id(self, bash_var: str) -> None:
        self._write_line(f"{bash_var}=$(lcli {self.idx} getinfo | jq -r '.id')")
    
    def wait_for_funds(self) -> None:
        self._write_line(f"""
    while [[ $(lcli {self.idx} listfunds | jq -r ".outputs") == "[]" ]]; do
        sleep 1
    done
    """)
    
    def establish_channel(self, peer: LightningCommandsGenerator, peer_listen_port: int) -> None:
        bash_var = f"ID_{peer.idx}"
        peer.set_id(bash_var=bash_var)
        self._write_line(f"lcli {self.idx} connect ${bash_var} localhost:{peer_listen_port}")
        self._write_line(f"lcli {self.idx} fundchannel ${bash_var} {INITIAL_CHANNEL_BALANCE_SAT}")
    
    def __set_riskfactor(self) -> None:
        self._write_line("RISKFACTOR=1")
    
    def wait_to_route(self, receiver: LightningCommandsGenerator, amount_msat: int) -> None:
        self.__set_riskfactor()
        receiver.set_id(bash_var="RECEIVER_ID")
        self._write_line(f"""
    while [[ "$(lcli {self.idx} getroute $RECEIVER_ID {amount_msat} $RISKFACTOR | jq -r ".route")" == "null" ]]; do
        sleep 1;
    done
        """)
    
    def create_invoice(self, payment_hash_bash_var, amount_msat: int) -> None:
        self._write_line(f"""LABEL="invoice-label-$(date +%s.%N)" """)
        self._write_line(
            f"""{payment_hash_bash_var}=$(lcli {self.idx} invoice {amount_msat} $LABEL "" | jq -r ".payment_hash")"""
        )
    
    def make_payments(
        self,
        receiver: LightningCommandsGenerator,
        num_payments: int,
        amount_msat: int,
    ) -> None:
        self.__set_riskfactor()
        receiver.set_id(bash_var="RECEIVER_ID")
        self._write_line(f"for i in $(seq 1 {num_payments}); do")
        receiver.create_invoice(payment_hash_bash_var="PAYMENT_HASH", amount_msat=amount_msat)
        self._write_line(
            f"""ROUTE=$(lcli {self.idx} getroute $RECEIVER_ID {amount_msat} $RISKFACTOR | jq -r ".route")""")
        self._write_line(f"""lcli {self.idx} sendpay "$ROUTE" "$PAYMENT_HASH" > /dev/null""")
        self._write_line("done")
    
    def print_node_htlcs(self) -> None:
        self._write_line(
            f"""lcli {self.idx} listpeers| jq ".peers[] | .channels[0].htlcs" | jq length"""
        )
    
    def close_all_channels(self) -> None:
        self._write_line(
            f"""PEER_IDS=$(lcli {self.idx} listpeers | jq -r ".peers[] | .id")"""
        )
        self._write_line(f"""
    for id in $PEER_IDS; do
        lcli {self.idx} close $id {CLOSE_CHANNEL_TIMEOUT_SEC}
    done
        """)
    
    def dump_balance(self, filepath: str) -> None:
        self._write_line(f"""printf "node {self.idx} balance: " >> {filepath}""")
        self._write_line(f"lcli {self.idx} listfunds | jq '.outputs[] | .value' | jq -s add >> {filepath}")
