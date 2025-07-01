import {
  Box,
  Table,
  TableBody,
  TableContainer,
  TableRow,
  TableCell,
  Paper,
  IconButton,
  Typography,
  TableHead,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { useScanContext } from "../../hooks/useScanContext";
import { ParameterCard } from "./ParameterCard";

export const ScanParameterTable = () => {
  const { state, dispatch } = useScanContext();

  return (
    <Box
      display="flex"
      flexDirection="column"
      sx={{ width: "400px", maxHeight: "600px" }}
    >
      <TableContainer component={Paper} sx={{ overflowY: "auto", maxHeight: "400px" }}>
        <Table stickyHeader size="small">
          <TableHead>
            <TableRow>
              <TableCell colSpan={2} align="center">
                <Typography>Scan Parameters</Typography>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {state.parameters.map((param, index) => (
              <TableRow key={index}>
                <TableCell width="5%" sx={{ py: 0, pr: 0 }}>
                  {index + 1}
                </TableCell>
                <TableCell>
                  <ParameterCard param={param} index={index} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Box display="flex" justifyContent="center">
          <IconButton onClick={() => dispatch({ type: "ADD_PARAMETER" })}>
            <AddIcon />
          </IconButton>
        </Box>
      </TableContainer>
    </Box>
  );
};

export default ScanParameterTable;
