import {
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
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "400px",
        maxHeight: "600px",
      }}
    >
      <TableContainer component={Paper} sx={{ overflowY: "auto", maxHeight: "450px" }}>
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
        <div style={{ display: "flex", justifyContent: "center" }}>
          <IconButton onClick={() => dispatch({ type: "ADD_PARAMETER" })}>
            <AddIcon />
          </IconButton>
        </div>
      </TableContainer>
    </div>
  );
};

export default ScanParameterTable;
