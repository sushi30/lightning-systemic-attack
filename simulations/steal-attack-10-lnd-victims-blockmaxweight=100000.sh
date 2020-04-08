#!/usr/bin/env bash
SCRIPT_NAME="steal-attack-10-lnd-victims-blockmaxweight=100000"
TOPOLOGY="$LN/topologies/topology-10-lnd-victims.json"
DATA_DIR="$LN/simulations/$SCRIPT_NAME"
OUTPUT_FILE="$LN/simulations/$SCRIPT_NAME.out"
SIMULATION=6
COMMANDS_FILE=$LN/generated_commands_$SIMULATION
cd $LN/py
python3 -m commands_generator.commands_generator \
    --topology "$TOPOLOGY" \
    --establish-channels \
    --make-payments 1 3 14490 11000000 \
    --steal-attack 1 3 150 \
    --dump-data "$DATA_DIR" \
    --block-time 180 \
    --bitcoin-blockmaxweight 100000 \
    --simulation-number $SIMULATION \
    --outfile $COMMANDS_FILE

rm -rf /tmp/lightning-simulations/$SIMULATION
bash $COMMANDS_FILE 2>&1 | tee "$OUTPUT_FILE"
