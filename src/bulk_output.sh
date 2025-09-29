#!/bin/bash
# Test script that outputs a large number of lines in bulk
# to verify the daemon and database can handle it correctly

echo "Starting bulk output test..."

# First batch: Output 10,000 lines
echo "First batch of 10,000 lines complete"
for i in $(seq 1 10000); do
    printf "BATCH1 Line #%05d: This is test output from the first batch with some content to make it realistic\n" "$i"
done

echo "First batch of 10,000 lines complete"
sleep 1  # Small pause between batches

# Second batch: Output another 10,000 lines
for i in $(seq 10001 20000); do
    printf "BATCH2 Line #%05d: This is test output from the second batch with different content for variety\n" "$i"
done

echo "Second batch of 10,000 lines complete"
echo "Test complete: Output total of 20,000 lines"